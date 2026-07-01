from datetime import date
from decimal import Decimal

from finsight_common.agent import TransactionStore
from finsight_common.config import Settings
from finsight_common.models import Category, Transaction
from finsight_common.warehouse import SnowflakeTransactionStore, get_transaction_store


class FakeCursor:
    def __init__(self, rows=None):
        self.executed: list = []
        self.many: list = []
        self._rows = rows or []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def executemany(self, sql, seq):
        self.many.append((sql, list(seq)))

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, rows=None):
        self.cursor_obj = FakeCursor(rows)

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        pass

    def close(self):
        pass


def _cfg():
    return Settings(snowflake_account="a", snowflake_user="u", snowflake_password="p")


def test_factory_defaults_to_in_memory():
    assert isinstance(get_transaction_store(Settings()), TransactionStore)


def test_factory_returns_snowflake_when_configured():
    assert isinstance(get_transaction_store(_cfg()), SnowflakeTransactionStore)


def test_add_builds_fact_rows_and_replaces_by_source():
    conn = FakeConn()
    store = SnowflakeTransactionStore(_cfg(), connect=lambda: conn)
    store.add(
        [
            Transaction(
                txn_date=date(2024, 3, 1),
                description="Swiggy",
                amount=Decimal("-450"),
                category=Category.DINING,
            ),
            Transaction(
                txn_date=date(2024, 3, 2),
                description="Salary",
                amount=Decimal("50000"),
                category=Category.INCOME,
            ),
        ],
        source_id="march.csv",
    )
    cur = conn.cursor_obj
    assert any("DELETE FROM FACT_TRANSACTION" in sql for sql, _ in cur.executed)
    rows = cur.many[0][1]
    assert len(rows) == 2
    assert rows[0][0] == "march.csv:0"  # txn_id
    assert rows[0][3] == "Swiggy"  # description
    assert rows[0][5] is True  # is_outflow
    assert rows[1][5] is False  # inflow


def test_all_reconstructs_transactions():
    rows = [
        (date(2024, 3, 1), "Swiggy", -450.0, "dining", "INR"),
        (date(2024, 3, 2), "Salary", 50000.0, "income", "INR"),
    ]
    store = SnowflakeTransactionStore(_cfg(), connect=lambda: FakeConn(rows))
    result = store.all()
    assert [t.description for t in result] == ["Swiggy", "Salary"]
    assert result[0].amount == Decimal("-450.0")
    assert result[0].category == Category.DINING
    assert result[1].category == Category.INCOME


def test_add_empty_is_noop():
    conn = FakeConn()
    SnowflakeTransactionStore(_cfg(), connect=lambda: conn).add([])
    assert conn.cursor_obj.executed == []
    assert conn.cursor_obj.many == []
