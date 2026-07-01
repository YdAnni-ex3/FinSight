"""Persistent transaction store backed by a Snowflake star schema.

When Snowflake is configured, analyzed statements load into a star schema
(DIM_DATE, DIM_CATEGORY, FACT_TRANSACTION) and the agent/analytics read back
from it, so state survives restarts and is shared across replicas. Otherwise the
factory returns the in-process store. The connector is imported lazily, and the
connection is injectable so the logic is testable without a live warehouse.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from .agent import TransactionStore
from .config import Settings, get_settings
from .models import Category, Transaction

# Deterministic category keys (index in the enum), seeded into DIM_CATEGORY.
_CATEGORY_KEY = {c.value: i for i, c in enumerate(Category)}
_OTHER_KEY = _CATEGORY_KEY[Category.OTHER.value]

_MERGE_DATE = (
    "MERGE INTO DIM_DATE t USING (SELECT %s AS date_key) s ON t.date_key = s.date_key "
    "WHEN NOT MATCHED THEN INSERT (date_key, full_date, year, month, day, month_name, weekday) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)
_INSERT_FACT = (
    "INSERT INTO FACT_TRANSACTION "
    "(txn_id, date_key, category_key, description, amount, is_outflow, currency, source_file) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
)
_SELECT_ALL = (
    "SELECT d.full_date, f.description, f.amount, c.category_name, f.currency "
    "FROM FACT_TRANSACTION f "
    "JOIN DIM_DATE d ON f.date_key = d.date_key "
    "LEFT JOIN DIM_CATEGORY c ON f.category_key = c.category_key "
    "ORDER BY d.full_date, f.txn_id"
)


class SnowflakeTransactionStore:
    """Loads transactions into, and reads them back from, the Snowflake star schema."""

    def __init__(self, settings: Settings, connect: Callable | None = None) -> None:
        self._settings = settings
        self._connect = connect or self._default_connect

    def _default_connect(self):  # pragma: no cover - needs the connector + credentials
        import snowflake.connector

        s = self._settings
        return snowflake.connector.connect(
            account=s.snowflake_account,
            user=s.snowflake_user,
            password=s.snowflake_password,
            warehouse=s.snowflake_warehouse,
            database=s.snowflake_database,
            schema=s.snowflake_schema,
            role=s.snowflake_role or None,
        )

    def add(self, transactions: list[Transaction], source_id: str = "upload") -> None:
        if not transactions:
            return

        fact_rows = [
            (
                f"{source_id}:{i}",
                int(t.txn_date.strftime("%Y%m%d")),
                _CATEGORY_KEY.get((t.category or Category.OTHER).value, _OTHER_KEY),
                t.description,
                float(t.amount),
                t.amount < 0,
                t.currency,
                source_id,
            )
            for i, t in enumerate(transactions)
        ]

        conn = self._connect()
        try:
            cur = conn.cursor()
            for d in {t.txn_date for t in transactions}:
                dk = int(d.strftime("%Y%m%d"))
                cur.execute(
                    _MERGE_DATE,
                    (
                        dk,
                        dk,
                        d.isoformat(),
                        d.year,
                        d.month,
                        d.day,
                        d.strftime("%B"),
                        d.strftime("%A"),
                    ),
                )
            # Idempotent per source: replace this file's rows, then bulk-insert.
            cur.execute("DELETE FROM FACT_TRANSACTION WHERE source_file = %s", (source_id,))
            cur.executemany(_INSERT_FACT, fact_rows)
            conn.commit()
        finally:
            conn.close()

    def all(self) -> list[Transaction]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(_SELECT_ALL)
            rows = cur.fetchall()
        finally:
            conn.close()

        valid = {c.value for c in Category}
        transactions: list[Transaction] = []
        for full_date, description, amount, category, currency in rows:
            if isinstance(full_date, datetime):
                txn_date = full_date.date()
            elif isinstance(full_date, date):
                txn_date = full_date
            else:
                txn_date = datetime.strptime(str(full_date), "%Y-%m-%d").date()
            transactions.append(
                Transaction(
                    txn_date=txn_date,
                    description=description,
                    amount=Decimal(str(amount)),
                    currency=currency or "INR",
                    category=Category(category) if category in valid else None,
                )
            )
        return transactions


def get_transaction_store(settings: Settings | None = None):
    """Return the Snowflake-backed store when configured, else the in-process store."""
    settings = settings or get_settings()
    if settings.snowflake_configured:
        return SnowflakeTransactionStore(settings)
    return TransactionStore()
