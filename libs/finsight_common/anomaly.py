"""Anomaly detection over a parsed statement.

Statistical + rule-based flags on outflows: unusually large transactions
(robust outliers vs. the median) and likely duplicate charges. Deterministic
and dependency-free, so it runs anywhere and is easy to test. This is the
baseline the ML model (later phase) must beat.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from pydantic import BaseModel

from .models import Statement, Transaction

# Ignore "large" flags below this absolute magnitude to avoid noise on tiny amounts.
_LARGE_FLOOR = 1000.0


class Anomaly(BaseModel):
    type: str  # "large_transaction" | "possible_duplicate"
    severity: str  # "low" | "medium" | "high"
    message: str
    transactions: list[dict]


def _txn_view(txn: Transaction) -> dict:
    return {
        "date": txn.txn_date.isoformat(),
        "description": txn.description,
        "amount": float(txn.amount),
        "category": txn.category.value if txn.category else "other",
    }


def _large_transactions(outflows: list[Transaction]) -> list[Anomaly]:
    magnitudes = [float(-t.amount) for t in outflows]
    if len(magnitudes) < 3:
        return []
    median = statistics.median(magnitudes)
    if median <= 0:
        return []
    threshold = median * 4
    anomalies: list[Anomaly] = []
    for txn in outflows:
        magnitude = float(-txn.amount)
        if magnitude > threshold and magnitude > _LARGE_FLOOR:
            severity = "high" if magnitude > median * 8 else "medium"
            anomalies.append(
                Anomaly(
                    type="large_transaction",
                    severity=severity,
                    message=(
                        f"Unusually large charge of {magnitude:,.0f} "
                        f"(~{magnitude / median:.0f}x your typical spend)"
                    ),
                    transactions=[_txn_view(txn)],
                )
            )
    return anomalies


def _duplicates(outflows: list[Transaction]) -> list[Anomaly]:
    groups: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for txn in outflows:
        groups[(txn.description, str(txn.amount))].append(txn)

    anomalies: list[Anomaly] = []
    for (description, _amount), items in groups.items():
        if len(items) >= 2:
            magnitude = float(-items[0].amount)
            anomalies.append(
                Anomaly(
                    type="possible_duplicate",
                    severity="high" if magnitude > _LARGE_FLOOR else "medium",
                    message=(
                        f"{len(items)} identical charges of {magnitude:,.0f} for '{description}'"
                    ),
                    transactions=[_txn_view(t) for t in items],
                )
            )
    return anomalies


def detect_anomalies(statement: Statement) -> list[Anomaly]:
    """Return anomalies found in a statement's outflows."""
    outflows = [t for t in statement.transactions if t.amount < 0]
    return _large_transactions(outflows) + _duplicates(outflows)
