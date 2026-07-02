"""Tests for the ML anomaly layer (features + IsolationForest + merge logic)."""

import pytest

pytest.importorskip("sklearn")

from datetime import date  # noqa: E402
from decimal import Decimal  # noqa: E402

from finsight_common.anomaly import (  # noqa: E402
    Anomaly,
    combine_anomalies,
    detect_ml_anomalies,
)
from finsight_common.ml import (  # noqa: E402
    FEATURE_NAMES,
    AnomalyModel,
    statement_feature_matrix,
)
from finsight_common.models import Category, Statement, Transaction  # noqa: E402


def _txn(desc: str, amount, day: int = 1, category: Category = Category.SHOPPING) -> Transaction:
    return Transaction(
        txn_date=date(2024, 3, day),
        description=desc,
        amount=Decimal(str(amount)),
        category=category,
    )


def _normal_statement(n: int = 30) -> Statement:
    return Statement(
        transactions=[_txn(f"Coffee shop {i}", -(100 + i), (i % 27) + 1) for i in range(n)]
    )


def test_feature_matrix_shape_matches_outflows():
    statement = _normal_statement()
    matrix, outflows = statement_feature_matrix(statement)
    assert len(matrix) == len(outflows) == 30
    assert all(len(row) == len(FEATURE_NAMES) for row in matrix)


def test_inflows_excluded_from_matrix():
    statement = Statement(
        transactions=[_txn("Salary", 50000, 1, Category.INCOME), _txn("Coffee", -100, 2)]
    )
    matrix, outflows = statement_feature_matrix(statement)
    assert len(matrix) == len(outflows) == 1


def test_model_flags_injected_outlier():
    train_matrix, _ = statement_feature_matrix(_normal_statement())
    model = AnomalyModel.fit(train_matrix, contamination=0.05)

    test_statement = Statement(
        transactions=[_txn(f"Coffee {i}", -(100 + i), (i % 27) + 1) for i in range(10)]
        + [_txn("Luxury watch boutique", -95000, 15)]
    )
    anomalies = detect_ml_anomalies(test_statement, model)
    flagged_amounts = {t["amount"] for a in anomalies for t in a.transactions}
    assert -95000.0 in flagged_amounts
    assert all(a.type == "ml_outlier" for a in anomalies)


def test_detect_ml_needs_minimum_transactions():
    model = AnomalyModel.fit(statement_feature_matrix(_normal_statement())[0])
    tiny = Statement(transactions=[_txn("Coffee", -100, 1), _txn("Tea", -120, 2)])
    assert detect_ml_anomalies(tiny, model) == []


def test_detect_ml_returns_empty_without_model():
    assert detect_ml_anomalies(_normal_statement(), None) == []


def test_model_save_and_load_roundtrip(tmp_path):
    matrix, _ = statement_feature_matrix(_normal_statement())
    model = AnomalyModel.fit(matrix)
    path = tmp_path / "model.joblib"
    model.save(path)

    loaded = AnomalyModel.load(path)
    assert loaded.feature_names == model.feature_names
    assert loaded.predict(matrix) == model.predict(matrix)


def test_combine_dedupes_ml_outlier_overlapping_a_rule_flag():
    txn_view = {
        "date": "2024-03-10",
        "description": "TV",
        "amount": -65000.0,
        "category": "shopping",
    }
    rule = Anomaly(
        type="large_transaction", severity="high", message="big", transactions=[txn_view]
    )
    dup = Anomaly(type="ml_outlier", severity="medium", message="ml", transactions=[txn_view])
    other = Anomaly(
        type="ml_outlier",
        severity="low",
        message="ml2",
        transactions=[
            {"date": "2024-03-11", "description": "X", "amount": -10.0, "category": "other"}
        ],
    )

    combined = combine_anomalies([rule], [dup, other])
    assert rule in combined
    assert dup not in combined
    assert other in combined
    assert len(combined) == 2
