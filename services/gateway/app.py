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
from finsight_common.agent import FinanceAgent
from finsight_common.analytics import spend_by_category
from finsight_common.anomaly import (
    combine_anomalies,
    detect_anomalies,
    detect_ml_anomalies,
    load_anomaly_model,
)
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
from finsight_common.vision import get_slip_extractor
from finsight_common.warehouse import get_transaction_store
from pydantic import BaseModel

from .metrics import (
    AGENT_QUERIES,
    ANOMALIES_DETECTED,
    STATEMENTS_ANALYZED,
    TRANSACTIONS_INGESTED,
    UPLOAD_PROCESSING,
    setup_metrics,
)

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

# Persistent (Snowflake) or in-process transaction store; the agent reasons over it.
_txn_store = get_transaction_store(settings)
_store_kind = "snowflake" if settings.snowflake_configured else "in-memory"
_agent = FinanceAgent(_txn_store, chat=_provider if settings.azure_openai_configured else None)

# Trained IsolationForest for anomaly detection; None (rules only) if unavailable.
_anomaly_model = load_anomaly_model(settings.anomaly_model_path)
_anomaly_ml = "isolation_forest" if _anomaly_model is not None else "disabled"

_slip_extractor = get_slip_extractor(settings)

app = FastAPI(title="FinSight Gateway", version=__version__)

# Prometheus /metrics + standard HTTP request/latency series (no-op without obs extra).
setup_metrics(app)

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
_ALLOWED_SLIP_MIMES: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "heic": "image/heic",
}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, object]:
    return {
        "status": "ready",
        "llm_provider": _provider.name,
        "azure_openai_configured": settings.azure_openai_configured,
        "transaction_store": _store_kind,
        "retrieval": _retrieval,
        "anomaly_ml": _anomaly_ml,
        "git_sha": settings.git_sha,
    }


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
    with UPLOAD_PROCESSING.time():
        filename, statement = await _process_upload(file)

    anomalies = combine_anomalies(
        detect_anomalies(statement),
        detect_ml_anomalies(statement, _anomaly_model),
    )
    indexed = _rag.index_statement(statement, source_id=filename)
    _txn_store.add(statement.transactions, source_id=filename)

    STATEMENTS_ANALYZED.inc()
    TRANSACTIONS_INGESTED.inc(len(statement.transactions))
    for anomaly in anomalies:
        ANOMALIES_DETECTED.labels(type=anomaly.type).inc()

    log.info(
        "statement.analyzed",
        filename=filename,
        transactions=len(statement.transactions),
        anomalies=len(anomalies),
        anomaly_ml=_anomaly_ml,
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
            "anomaly_ml": _anomaly_ml,
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


@app.post("/api/agent")
def agent_query(payload: QueryRequest) -> dict:
    """Answer a question with the tool-using finance agent (returns answer + steps)."""
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    AGENT_QUERIES.inc()
    return _agent.run(payload.question).model_dump()


@app.post("/api/slips/ingest")
async def ingest_slip(file: Annotated[UploadFile, File()]) -> dict:
    """Extract transactions from a finance slip photo/scan and run full analysis.

    Accepts JPEG, PNG, WEBP, GIF, BMP images (up to 10 MB). Uses a vision LLM
    (Azure OpenAI or Bedrock) to extract structured transactions, then runs them
    through the same pipeline as :func:`analyze_statement`.
    """
    filename = file.filename or "slip"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_SLIP_MIMES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported slip format '{ext}'. Accepted: jpg, jpeg, png, webp, gif, bmp, heic.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    mime_type = _ALLOWED_SLIP_MIMES[ext]

    transactions = _slip_extractor.extract(data, mime_type)
    if not transactions:
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not extract any transactions from this image. "
                "Try a clearer photo, or ensure the file contains readable text."
            ),
        )

    for txn in transactions:
        txn.description = redact_text(txn.description)

    statement = Statement(transactions=transactions)
    anomalies = combine_anomalies(
        detect_anomalies(statement),
        detect_ml_anomalies(statement, _anomaly_model),
    )
    indexed = _rag.index_statement(statement, source_id=filename)
    _txn_store.add(statement.transactions, source_id=filename)

    STATEMENTS_ANALYZED.inc()
    TRANSACTIONS_INGESTED.inc(len(transactions))
    for anomaly in anomalies:
        ANOMALIES_DETECTED.labels(type=anomaly.type).inc()

    log.info(
        "slip.ingested",
        filename=filename,
        transactions=len(transactions),
        anomalies=len(anomalies),
        extractor=type(_slip_extractor).__name__,
    )
    return {
        "statement": statement.model_dump(mode="json"),
        "summary": {
            "transaction_count": len(transactions),
            "total_inflow": float(statement.total_inflow),
            "total_outflow": float(statement.total_outflow),
            "net": float(statement.net),
            "categorizer": "vision_llm",
            "anomaly_count": len(anomalies),
            "anomaly_ml": _anomaly_ml,
            "indexed": indexed,
            "retrieval": _retrieval,
            "source": "slip",
            "extractor": type(_slip_extractor).__name__,
        },
        "by_category": spend_by_category(statement),
        "anomalies": [a.model_dump() for a in anomalies],
    }


@app.get("/api/analytics/spend")
def analytics_spend() -> dict:
    """Spend-by-category across ALL stored statements (uses the persistent store)."""
    statement = Statement(transactions=_txn_store.all())
    return {"store": _store_kind, "by_category": spend_by_category(statement)}
