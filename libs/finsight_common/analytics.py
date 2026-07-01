"""Lightweight spend analytics over a statement."""

from __future__ import annotations

from .models import Statement


def spend_by_category(statement: Statement) -> dict[str, float]:
    """Total outflow per category, sorted highest first (inflows excluded)."""
    totals: dict[str, float] = {}
    for txn in statement.transactions:
        if txn.amount < 0:
            category = txn.category.value if txn.category else "other"
            totals[category] = totals.get(category, 0.0) + float(-txn.amount)
    return dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))
