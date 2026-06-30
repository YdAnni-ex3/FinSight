"""Domain models shared across services.

Money is represented with :class:`~decimal.Decimal` for correctness and
serialized to JSON as floats so the frontend and API consumers get plain
numbers. Sign convention for ``amount``: **positive = inflow (credit),
negative = outflow (debit)**.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_serializer


class Category(StrEnum):
    """Canonical spend/income categories."""

    INCOME = "income"
    GROCERIES = "groceries"
    DINING = "dining"
    TRANSPORT = "transport"
    UTILITIES = "utilities"
    RENT = "rent"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    HEALTH = "health"
    TRAVEL = "travel"
    SUBSCRIPTIONS = "subscriptions"
    TRANSFERS = "transfers"
    FEES = "fees"
    OTHER = "other"


class Transaction(BaseModel):
    txn_date: date
    description: str
    amount: Decimal
    currency: str = "INR"
    balance: Decimal | None = None
    category: Category | None = None
    merchant: str | None = None
    raw: str | None = None

    @property
    def is_outflow(self) -> bool:
        return self.amount < 0

    @field_serializer("amount")
    def _serialize_amount(self, value: Decimal) -> float:
        return float(value)

    @field_serializer("balance")
    def _serialize_balance(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None


class Statement(BaseModel):
    account_holder: str | None = None
    account_number_masked: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    currency: str = "INR"
    source_filename: str | None = None
    transactions: list[Transaction] = Field(default_factory=list)

    @property
    def total_inflow(self) -> Decimal:
        return sum((t.amount for t in self.transactions if t.amount > 0), Decimal("0"))

    @property
    def total_outflow(self) -> Decimal:
        return sum((-t.amount for t in self.transactions if t.amount < 0), Decimal("0"))

    @property
    def net(self) -> Decimal:
        return self.total_inflow - self.total_outflow
