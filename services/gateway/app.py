"""FinSight API gateway.

The single entry point the frontend talks to. For the MVP it orchestrates the
core pipeline inline — parse -> redact PII -> categorize — and returns a
structured :class:`Statement`. As services split out (Phase 9+), these handlers
become thin proxies to the dedicated services.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from finsight_common import __version__, get_settings
from finsight_common.analytics import spend_by_category
from finsight_common.anomaly import detect_anomalies
from finsight_common.categorize import categorize_by_rules
from finsight_common.embeddings import get_embedding_provider
from finsight_common.llm import get_provider
from finsight_common.llm_categorize import llm_categorize
from finsight_common.logging import configure_logging, get_logger
from finsight_common.models import Statement
from finsight_common.parsing import StatementParseError, parse_bytes
from finsight_common.pii import redact_text
from finsight_common.rag import RagService
from finsight_common.vectorstore import get_vector_store
from pydantic import BaseModel

settings = get_settings()
configure_logging(settings.log_level, json_logs=settings.environment != "local")
log = get_logger("gateway")

# One provider instance per process. NullProvider when Azure OpenAI isn't
# configured, in which case we fall back to the deterministic rules categorizer.
_provider = get_provider(settings)
_categorizer = "llm" if settings.azure_openai_configured else "rules"

# RAG stack: Azure embeddings + Pinecone when configured, deterministic local
# embeddings + an in-memory store otherwise (so it runs with zero cloud).
_embedder = get_embedding_provider(settings)
_vector_store = get_vector_store(settings, dim=_embedder.dim)
_rag = RagService(
    _embedder,
    _vector_store,
    chat=_provider if settings.azure_openai_configured else None,
)
_retrieval = "pinecone" if settings.pinecone_api_key else "in-memory"

app = FastAPI(title="FinSight Gateway", version=__version__)

# CORS: "*" for local dev; in production set FINSIGHT_CORS_ORIGINS to the Vercel
# domain and FINSIGHT_CORS_ORIGIN_REGEX to also allow preview deployments.
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ALLOWED_SUFFIXES = (".csv", ".xlsx", ".xls", ".pdf")
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, object]:
    return {"status": "ready", "azure_openai_configured": settings.azure_openai_configured}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "finsight-gateway", "version": __version__}


async def _process_upload(file: UploadFile) -> tuple[str, Statement]:
    """Validate, read, parse, redact PII, and categorize an uploaded statement."""
    filename = file.filename or "upload"
    if not filename.lower().endswith(_ALLOWED_SUFFIXES):
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {filename}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    try:
        statement = parse_bytes(data, filename)
    except StatementParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Redact PII BEFORE anything external (incl. the LLM/embeddings) sees it.
    for txn in statement.transactions:
        txn.description = redact_text(txn.description)

    # Categorize: LLM when configured, deterministic rules otherwise.
    descriptions = [t.description for t in statement.transactions]
    if settings.azure_openai_configured:
        categories = llm_categorize(descriptions, _provider)
    else:
        categories = [categorize_by_rules(d) for d in descriptions]
    for txn, category in zip(statement.transactions, categories, strict=False):
        txn.category = category

    return filename, statement


@app.post("/api/statements/parse")
async def parse_statement(file: Annotated[UploadFile, File()]) -> dict:
    """Upload a statement, then parse, redact PII, and categorize it."""
    filename, statement = await _process_upload(file)
    log.info(
        "statement.parsed",
        filename=filename,
        transactions=len(statement.transactions),
        categorizer=_categorizer,
    )
    return {
        "statement": statement.model_dump(mode="json"),
        "summary": {
            "transaction_count": len(statement.transactions),
            "total_inflow": float(statement.total_inflow),
            "total_outflow": float(statement.total_outflow),
            "net": float(statement.net),
            "categorizer": _categorizer,
        },
    }


@app.post("/api/statements/index")
async def index_statement(file: Annotated[UploadFile, File()]) -> dict:
    """Upload a statement and index its transactions into the vector store."""
    filename, statement = await _process_upload(file)
    indexed = _rag.index_statement(statement, source_id=filename)
    log.info("statement.indexed", filename=filename, indexed=indexed, retrieval=_retrieval)
    return {"indexed": indexed, "retrieval": _retrieval}


@app.post("/api/statements/analyze")
async def analyze_statement(file: Annotated[UploadFile, File()]) -> dict:
    """Parse and categorize, compute spend-by-category and anomalies, and index for Q&A."""
    filename, statement = await _process_upload(file)
    anomalies = detect_anomalies(statement)
    indexed = _rag.index_statement(statement, source_id=filename)
    log.info(
        "statement.analyzed",
        filename=filename,
        transactions=len(statement.transactions),
        anomalies=len(anomalies),
        indexed=indexed,
    )
    return {
        "statement": statement.model_dump(mode="json"),
        "summary": {
            "transaction_count": len(statement.transactions),
            "total_inflow": float(statement.total_inflow),
            "total_outflow": float(statement.total_outflow),
            "net": float(statement.net),
            "categorizer": _categorizer,
            "anomaly_count": len(anomalies),
            "indexed": indexed,
            "retrieval": _retrieval,
        },
        "by_category": spend_by_category(statement),
        "anomalies": [a.model_dump() for a in anomalies],
    }


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


@app.post("/api/query")
def query(payload: QueryRequest) -> dict:
    """Answer a natural-language question over previously indexed statements."""
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    return _rag.query(payload.question, top_k=payload.top_k)
