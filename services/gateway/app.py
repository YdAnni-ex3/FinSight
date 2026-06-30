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
from finsight_common.categorize import categorize_statement
from finsight_common.logging import configure_logging, get_logger
from finsight_common.parsing import StatementParseError, parse_bytes
from finsight_common.pii import redact_text

settings = get_settings()
configure_logging(settings.log_level, json_logs=settings.environment != "local")
log = get_logger("gateway")

app = FastAPI(title="FinSight Gateway", version=__version__)

# Allow the local + deployed frontend to call the API. Tighten origins for prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.post("/api/statements/parse")
async def parse_statement(file: Annotated[UploadFile, File()]) -> dict:
    """Upload a statement, then parse, redact PII, and categorize it.

    Returns the structured statement plus a small summary. PII is redacted from
    every description before it is returned or (later) sent to any external LLM.
    """
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

    # Redact PII from descriptions, then categorize.
    for txn in statement.transactions:
        txn.description = redact_text(txn.description)
    statement = categorize_statement(statement)

    log.info(
        "statement.parsed",
        filename=filename,
        transactions=len(statement.transactions),
    )

    return {
        "statement": statement.model_dump(mode="json"),
        "summary": {
            "transaction_count": len(statement.transactions),
            "total_inflow": float(statement.total_inflow),
            "total_outflow": float(statement.total_outflow),
            "net": float(statement.net),
        },
    }
