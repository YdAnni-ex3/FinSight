from datetime import date
from decimal import Decimal

from finsight_common.embeddings import HashEmbeddingProvider
from finsight_common.models import Category, Statement, Transaction
from finsight_common.rag import RagService
from finsight_common.vectorstore import InMemoryVectorStore


def _statement() -> Statement:
    return Statement(
        transactions=[
            Transaction(
                txn_date=date(2024, 3, 1),
                description="Swiggy food order",
                amount=Decimal("-450"),
                category=Category.DINING,
            ),
            Transaction(
                txn_date=date(2024, 3, 2),
                description="Salary credit ACME",
                amount=Decimal("50000"),
                category=Category.INCOME,
            ),
            Transaction(
                txn_date=date(2024, 3, 3),
                description="Netflix subscription",
                amount=Decimal("-499"),
                category=Category.SUBSCRIPTIONS,
            ),
        ]
    )


def _rag(chat=None) -> RagService:
    return RagService(HashEmbeddingProvider(dim=256), InMemoryVectorStore(), chat=chat)


def test_index_returns_count():
    assert _rag().index_statement(_statement(), source_id="s") == 3


def test_query_retrieves_relevant_transaction():
    rag = _rag()
    rag.index_statement(_statement(), source_id="s")
    result = rag.query("how much did I spend on food?", top_k=1)
    assert result["matches"][0]["description"] == "Swiggy food order"


def test_query_uses_chat_when_available():
    class FakeChat:
        name = "fake"

        def chat(self, messages, *, temperature: float = 0.0) -> str:
            return "You spent 450 on food."

        def embed(self, texts):
            return [[0.0] for _ in texts]

    rag = _rag(chat=FakeChat())
    rag.index_statement(_statement(), source_id="s")
    assert rag.query("food spend?", top_k=2)["answer"] == "You spent 450 on food."


def test_query_extractive_fallback_without_chat():
    rag = _rag()
    rag.index_statement(_statement(), source_id="s")
    assert "Top matches:" in rag.query("netflix", top_k=1)["answer"]


def test_query_empty_store():
    result = _rag().query("anything", top_k=3)
    assert result["matches"] == []
    assert "No matching" in result["answer"]
