"""Prometheus metrics for the gateway.

Exposes ``GET /metrics`` (via prometheus-fastapi-instrumentator) with standard
HTTP request/latency series, plus a handful of domain counters. The whole
module is import-guarded: if the ``obs`` extra isn't installed the metrics
degrade to no-ops so the API still runs.
"""

from __future__ import annotations

from contextlib import nullcontext

try:
    from prometheus_client import Counter, Histogram
    from prometheus_fastapi_instrumentator import Instrumentator

    _ENABLED = True
except ImportError:  # pragma: no cover - obs extra not installed
    _ENABLED = False


if _ENABLED:
    STATEMENTS_ANALYZED = Counter(
        "finsight_statements_analyzed_total",
        "Statements processed by /api/statements/analyze",
    )
    TRANSACTIONS_INGESTED = Counter(
        "finsight_transactions_ingested_total",
        "Transactions parsed from uploaded statements",
    )
    ANOMALIES_DETECTED = Counter(
        "finsight_anomalies_detected_total",
        "Anomalies detected, labelled by type",
        ["type"],
    )
    AGENT_QUERIES = Counter(
        "finsight_agent_queries_total",
        "Questions answered by the finance agent",
    )
    UPLOAD_PROCESSING = Histogram(
        "finsight_upload_processing_seconds",
        "Time to parse, redact, and categorize an uploaded statement",
    )

    def setup_metrics(app) -> None:
        """Attach the Prometheus instrumentator and expose /metrics."""
        Instrumentator(
            should_group_status_codes=True,
            excluded_handlers=["/metrics", "/healthz", "/readyz"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

else:  # pragma: no cover - exercised only when the obs extra is absent

    class _Noop:
        def labels(self, *args, **kwargs) -> _Noop:
            return self

        def inc(self, *args, **kwargs) -> None:
            pass

        def observe(self, *args, **kwargs) -> None:
            pass

        def time(self):
            return nullcontext()

    STATEMENTS_ANALYZED = _Noop()
    TRANSACTIONS_INGESTED = _Noop()
    ANOMALIES_DETECTED = _Noop()
    AGENT_QUERIES = _Noop()
    UPLOAD_PROCESSING = _Noop()

    def setup_metrics(app) -> None:
        return None
