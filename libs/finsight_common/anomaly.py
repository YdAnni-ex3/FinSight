"""Anomaly detection over a parsed statement.

Statistical + rule-based flags on outflows: unusually large transactions
(robust outliers vs. the median) and likely duplicate charges. Deterministic
and dependency-free, so it runs anywhere and is easy to test. This is the
baseline the ML model (later phase) must beat.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from pathlib import Path

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
    """Return rule/statistical anomalies found in a statement's outflows."""
    outflows = [t for t in statement.transactions if t.amount < 0]
    return _large_transactions(outflows) + _duplicates(outflows)


# --- ML layer (IsolationForest) -------------------------------------------------
# The rule detector above is the deterministic baseline; the model below adds a
# learned signal that catches multi-feature outliers the rules miss. Both run and
# their results are merged (see :func:`combine_anomalies`).


def _severity_from_score(score: float) -> str:
    if score < -0.15:
        return "high"
    if score < -0.05:
        return "medium"
    return "low"


def detect_ml_anomalies(
    statement: Statement,
    model: object | None,
    *,
    min_transactions: int = 5,
) -> list[Anomaly]:
    """Flag outflows the anomaly model scores as outliers.

    Returns an empty list when the model is unavailable or there are too few
    transactions to give the model useful within-statement context.
    """
    if model is None:
        return []

    from .ml.features import statement_feature_matrix

    matrix, outflows = statement_feature_matrix(statement)
    if len(outflows) < min_transactions:
        return []

    scores = model.decision_scores(matrix)
    predictions = model.predict(matrix)
    anomalies: list[Anomaly] = []
    for txn, score, prediction in zip(outflows, scores, predictions, strict=False):
        if prediction == -1:
            anomalies.append(
                Anomaly(
                    type="ml_outlier",
                    severity=_severity_from_score(score),
                    message=(
                        f"ML model flagged this as unusual for your spending pattern "
                        f"(anomaly score {score:+.3f})"
                    ),
                    transactions=[_txn_view(txn)],
                )
            )
    return anomalies


def _txn_keys(anomaly: Anomaly) -> set[tuple[str, str, float]]:
    return {(t["date"], t["description"], t["amount"]) for t in anomaly.transactions}


def combine_anomalies(
    rule_anomalies: list[Anomaly],
    ml_anomalies: list[Anomaly],
) -> list[Anomaly]:
    """Merge rule + ML anomalies, dropping ML outliers already flagged by a rule."""
    seen: set[tuple[str, str, float]] = set()
    for anomaly in rule_anomalies:
        seen |= _txn_keys(anomaly)
    deduped = [a for a in ml_anomalies if not (_txn_keys(a) & seen)]
    return rule_anomalies + deduped


def load_anomaly_model(path: str | None) -> object | None:
    """Load a persisted anomaly model, or ``None`` if it can't be used.

    Never raises: a missing file or a missing ML dependency simply disables the
    ML layer, leaving the rule-based detector fully functional.
    """
    if not path or not Path(path).exists():
        return None
    try:
        from .ml.anomaly_model import AnomalyModel

        return AnomalyModel.load(path)
    except Exception:  # pragma: no cover - defensive: corrupt file / missing sklearn
        return None
