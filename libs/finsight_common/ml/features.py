"""Feature engineering for the ML anomaly model.

Each outflow transaction becomes a small numeric vector. Crucially, the
amount-based features are normalized *within a statement* (ratio and z-score
vs. that statement's own spending) so a single :class:`IsolationForest`
generalizes across users with very different absolute spend levels — a
₹5,000 charge is unremarkable for one account and a huge outlier for another.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from ..models import Category, Statement, Transaction

# Order matters: this is the column order of the feature matrix the model sees.
FEATURE_NAMES: list[str] = [
    "log_amount",
    "amount_to_median_ratio",
    "amount_zscore",
    "is_round_amount",
    "day_of_week",
    "day_of_month",
    "is_weekend",
    "is_month_boundary",
    "desc_length",
    "desc_word_count",
    "desc_has_digits",
    "category_code",
]

_CATEGORIES: list[Category] = list(Category)


@dataclass(frozen=True)
class StatementStats:
    """Per-statement spend statistics used to normalize amount features."""

    median: float
    mean: float
    std: float

    @classmethod
    def from_outflows(cls, outflows: list[Transaction]) -> StatementStats:
        magnitudes = [float(-t.amount) for t in outflows] or [0.0]
        median = statistics.median(magnitudes)
        mean = statistics.fmean(magnitudes)
        std = statistics.pstdev(magnitudes) if len(magnitudes) > 1 else 0.0
        return cls(median=median, mean=mean, std=std)


def transaction_features(txn: Transaction, stats: StatementStats) -> list[float]:
    """Turn one outflow transaction into a numeric feature vector."""
    magnitude = float(-txn.amount)
    median = stats.median or 1.0
    std = stats.std or 1.0
    description = txn.description or ""
    category = txn.category or Category.OTHER
    return [
        math.log1p(magnitude),
        magnitude / median,
        (magnitude - stats.mean) / std,
        1.0 if magnitude and magnitude % 100 == 0 else 0.0,
        float(txn.txn_date.weekday()),
        float(txn.txn_date.day),
        1.0 if txn.txn_date.weekday() >= 5 else 0.0,
        1.0 if txn.txn_date.day <= 3 or txn.txn_date.day >= 27 else 0.0,
        float(len(description)),
        float(len(description.split())),
        1.0 if any(ch.isdigit() for ch in description) else 0.0,
        float(_CATEGORIES.index(category)),
    ]


def _outflows(statement: Statement) -> list[Transaction]:
    return [t for t in statement.transactions if t.amount < 0]


def statement_feature_matrix(
    statement: Statement,
) -> tuple[list[list[float]], list[Transaction]]:
    """Return ``(feature_matrix, outflow_transactions)`` aligned row-for-row."""
    outflows = _outflows(statement)
    stats = StatementStats.from_outflows(outflows)
    matrix = [transaction_features(t, stats) for t in outflows]
    return matrix, outflows
