"""Transaction categorization.

A deterministic keyword rules engine assigns a :class:`Category` to each
transaction. This is the offline default (no cloud needed) and the baseline the
LLM categorizer (Phase 4) must beat. The LLM path is added later behind the
same interface.
"""

from __future__ import annotations

from .models import Category, Statement, Transaction

# Keyword -> Category. First match wins, so keep distinctive terms early.
_RULES: list[tuple[Category, tuple[str, ...]]] = [
    (Category.INCOME, ("salary", "payroll", "interest credit", "refund", "cashback")),
    (Category.RENT, ("rent", "landlord", "lease")),
    (Category.GROCERIES, ("grocery", "supermarket", "bigbasket", "dmart", "more retail", "zepto")),
    (
        Category.DINING,
        ("restaurant", "cafe", "swiggy", "zomato", "dominos", "mcdonald", "starbucks"),
    ),
    (Category.TRANSPORT, ("uber", "ola", "fuel", "petrol", "metro", "irctc", "fastag", "rapido")),
    (
        Category.UTILITIES,
        ("electricity", "water bill", "gas", "broadband", "mobile recharge", "airtel", "jio"),
    ),
    (
        Category.SUBSCRIPTIONS,
        ("netflix", "spotify", "prime", "subscription", "youtube premium", "hotstar"),
    ),
    (Category.SHOPPING, ("amazon", "flipkart", "myntra", "ajio", "shopping", "mall")),
    (Category.ENTERTAINMENT, ("bookmyshow", "pvr", "cinema", "gaming", "steam")),
    (Category.HEALTH, ("pharmacy", "apollo", "hospital", "clinic", "medical", "1mg", "pharmeasy")),
    (Category.TRAVEL, ("makemytrip", "goibibo", "indigo", "airlines", "hotel", "oyo", "airbnb")),
    (Category.FEES, ("fee", "charge", "penalty", "gst", "service tax")),
    (Category.TRANSFERS, ("upi", "neft", "imps", "transfer", "atm", "withdrawal")),
]


def categorize_by_rules(description: str) -> Category:
    """Return the best-guess category for a transaction description."""
    text = description.lower()
    for category, keywords in _RULES:
        if any(keyword in text for keyword in keywords):
            return category
    return Category.OTHER


def categorize_transaction(txn: Transaction) -> Transaction:
    """Return a copy of ``txn`` with ``category`` populated when missing."""
    if txn.category is not None:
        return txn
    return txn.model_copy(update={"category": categorize_by_rules(txn.description)})


def categorize_statement(statement: Statement) -> Statement:
    """Categorize every transaction in a statement in place-ish (returns a copy)."""
    return statement.model_copy(
        update={"transactions": [categorize_transaction(t) for t in statement.transactions]}
    )
