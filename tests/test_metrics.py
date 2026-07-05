"""Smoke tests for the Prometheus /metrics endpoint."""

import pytest

pytest.importorskip("pandas")
pytest.importorskip("prometheus_client")

from fastapi.testclient import TestClient  # noqa: E402

from services.gateway.app import app  # noqa: E402

client = TestClient(app)


def test_metrics_endpoint_exposes_custom_counters():
    # Generate a little traffic so HTTP series exist too.
    client.get("/healthz")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # Custom counters are registered at import time, so they appear even at 0.
    assert "finsight_statements_analyzed_total" in body
    assert "finsight_agent_queries_total" in body


def test_readyz_reports_anomaly_ml_field():
    body = client.get("/readyz").json()
    assert "anomaly_ml" in body
    assert body["anomaly_ml"] in {"isolation_forest", "disabled"}
    assert "git_sha" in body
