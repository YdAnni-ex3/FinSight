from datetime import date
from decimal import Decimal

from finsight_common.agent import FinanceAgent, TransactionStore
from finsight_common.models import Category, Transaction


class ScriptedProvider:
    """Returns canned chat responses in order (to script the ReAct loop)."""

    name = "scripted"

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list = []

    def chat(self, messages, *, temperature: float = 0.0) -> str:
        self.calls.append(messages)
        return self._responses.pop(0) if self._responses else '{"action":"answer","answer":"done"}'

    def embed(self, texts):
        return [[0.0] for _ in texts]


def _store() -> TransactionStore:
    store = TransactionStore()
    store.add(
        [
            Transaction(
                txn_date=date(2024, 3, 1),
                description="Swiggy dinner",
                amount=Decimal("-450"),
                category=Category.DINING,
            ),
            Transaction(
                txn_date=date(2024, 3, 2),
                description="BigBasket",
                amount=Decimal("-2000"),
                category=Category.GROCERIES,
            ),
            Transaction(
                txn_date=date(2024, 3, 3),
                description="Salary",
                amount=Decimal("50000"),
                category=Category.INCOME,
            ),
            Transaction(
                txn_date=date(2024, 3, 4),
                description="TV megastore",
                amount=Decimal("-65000"),
                category=Category.SHOPPING,
            ),
        ]
    )
    return store


# ---- offline fallback (no LLM) ----


def test_fallback_total_spend_by_category():
    result = FinanceAgent(_store()).run("How much did I spend on groceries?")
    assert result.steps[0].tool == "total_spend"
    assert result.steps[0].result["total"] == 2000.0
    assert "2,000" in result.answer


def test_fallback_anomalies():
    result = FinanceAgent(_store()).run("Any unusual charges?")
    assert result.steps[0].tool == "list_anomalies"
    assert result.steps[0].result["count"] >= 1


def test_fallback_breakdown():
    result = FinanceAgent(_store()).run("Show my spend breakdown by category")
    assert result.steps[0].tool == "spend_breakdown"
    assert "shopping" in result.steps[0].result["by_category"]


def test_fallback_search():
    result = FinanceAgent(_store()).run("swiggy")
    assert result.steps[0].tool == "search_transactions"
    assert result.steps[0].result["count"] == 1


# ---- LLM ReAct loop (scripted) ----


def test_llm_loop_calls_tool_then_answers():
    provider = ScriptedProvider(
        [
            '{"action":"tool","tool":"total_spend","arguments":{"category":"shopping"}}',
            '{"action":"answer","answer":"You spent 65,000 on shopping."}',
        ]
    )
    result = FinanceAgent(_store(), chat=provider).run("How much on shopping?")
    assert result.answer == "You spent 65,000 on shopping."
    assert len(result.steps) == 1
    assert result.steps[0].tool == "total_spend"
    assert result.steps[0].result["total"] == 65000.0


def test_llm_unknown_tool_is_recovered():
    provider = ScriptedProvider(
        [
            '{"action":"tool","tool":"nope","arguments":{}}',
            '{"action":"answer","answer":"recovered"}',
        ]
    )
    result = FinanceAgent(_store(), chat=provider).run("hmm")
    assert result.answer == "recovered"
    assert result.steps == []


def test_llm_error_falls_back_to_router():
    class Boom:
        name = "boom"

        def chat(self, messages, *, temperature: float = 0.0):
            raise RuntimeError("down")

        def embed(self, texts):
            return []

    result = FinanceAgent(_store(), chat=Boom()).run("any anomalies?")
    assert result.steps[0].tool == "list_anomalies"


def test_empty_statement_helper_stays_safe():
    result = FinanceAgent(TransactionStore()).run("how much did I spend?")
    assert result.steps[0].result["total"] == 0.0
