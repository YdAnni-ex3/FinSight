import pytest

pytest.importorskip("pandas")

from fastapi.testclient import TestClient  # noqa: E402

from services.gateway.app import app  # noqa: E402

client = TestClient(app)

_CSV = (
    b"Date,Description,Debit,Credit,Balance\n"
    b"2024-03-01,Salary credit ACME,,50000,50000\n"
    b"2024-03-02,UPI to ramesh@okhdfcbank 9876543210,450,,49550\n"
)


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_root_reports_service():
    body = client.get("/").json()
    assert body["service"] == "finsight-gateway"


def test_parse_endpoint_redacts_and_categorizes():
    resp = client.post(
        "/api/statements/parse",
        files={"file": ("march.csv", _CSV, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["summary"]["transaction_count"] == 2
    assert body["summary"]["total_inflow"] == 50000.0
    assert body["summary"]["total_outflow"] == 450.0

    descriptions = [t["description"] for t in body["statement"]["transactions"]]
    joined = " ".join(descriptions)
    assert "ramesh@okhdfcbank" not in joined  # email redacted
    assert "9876543210" not in joined  # phone redacted
    assert "<EMAIL>" in joined


def test_parse_rejects_unsupported_type():
    resp = client.post(
        "/api/statements/parse",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415


def test_index_and_query_flow():
    idx = client.post(
        "/api/statements/index",
        files={"file": ("march.csv", _CSV, "text/csv")},
    )
    assert idx.status_code == 200
    assert idx.json()["indexed"] == 2

    resp = client.post("/api/query", json={"question": "salary", "top_k": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body
    assert len(body["matches"]) == 1
    assert "Salary" in body["matches"][0]["description"]


def test_query_requires_question():
    assert client.post("/api/query", json={"question": "   "}).status_code == 400


def test_analyze_returns_categories_anomalies_and_breakdown():
    resp = client.post(
        "/api/statements/analyze",
        files={"file": ("march.csv", _CSV, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["transaction_count"] == 2
    assert "anomaly_count" in body["summary"]
    assert isinstance(body["by_category"], dict)
    assert isinstance(body["anomalies"], list)


def test_agent_answers_over_analyzed_statement():
    client.post("/api/statements/analyze", files={"file": ("march.csv", _CSV, "text/csv")})
    resp = client.post("/api/agent", json={"question": "how much did I spend in total?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"]
    assert isinstance(body["steps"], list)
    assert body["steps"][0]["tool"] == "total_spend"
