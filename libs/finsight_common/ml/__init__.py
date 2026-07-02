"""Machine-learning components: feature engineering + the anomaly model.

Kept in its own subpackage so the heavy ML dependencies (numpy, scikit-learn,
joblib) load lazily — importing :mod:`finsight_common` stays cheap and works
without the ``ml`` extra installed.
"""

from .anomaly_model import AnomalyModel
from .features import (
    FEATURE_NAMES,
    StatementStats,
    statement_feature_matrix,
    transaction_features,
)

__all__ = [
    "AnomalyModel",
    "FEATURE_NAMES",
    "StatementStats",
    "statement_feature_matrix",
    "transaction_features",
]
