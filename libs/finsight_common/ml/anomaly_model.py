"""IsolationForest anomaly model, persisted with joblib.

Wraps a scikit-learn ``Pipeline(StandardScaler -> IsolationForest)`` behind a
tiny API the rest of the app uses. Heavy imports (numpy, scikit-learn, joblib)
are done lazily inside methods so importing this module is cheap and doesn't
require the ``ml`` extra just to reference the class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .features import FEATURE_NAMES


@dataclass
class AnomalyModel:
    """A fitted anomaly-detection pipeline plus its metadata."""

    pipeline: Any
    feature_names: list[str] = field(default_factory=lambda: list(FEATURE_NAMES))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def fit(
        cls,
        matrix: list[list[float]],
        *,
        contamination: float = 0.03,
        n_estimators: int = 150,
        random_state: int = 42,
        feature_names: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnomalyModel:
        """Fit a scaler + IsolationForest on a feature matrix."""
        import numpy as np
        from sklearn.ensemble import IsolationForest
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        features = np.asarray(matrix, dtype=float)
        pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "iforest",
                    IsolationForest(
                        n_estimators=n_estimators,
                        contamination=contamination,
                        random_state=random_state,
                    ),
                ),
            ]
        )
        pipeline.fit(features)
        meta = {
            "contamination": contamination,
            "n_estimators": n_estimators,
            "n_samples": int(features.shape[0]),
            "n_features": int(features.shape[1]),
            **(metadata or {}),
        }
        return cls(
            pipeline=pipeline,
            feature_names=feature_names or list(FEATURE_NAMES),
            metadata=meta,
        )

    def decision_scores(self, matrix: list[list[float]]) -> list[float]:
        """Signed anomaly scores; lower (more negative) means more anomalous."""
        import numpy as np

        if not matrix:
            return []
        features = np.asarray(matrix, dtype=float)
        return self.pipeline.decision_function(features).tolist()

    def predict(self, matrix: list[list[float]]) -> list[int]:
        """Per-row labels: ``+1`` = normal, ``-1`` = anomaly."""
        import numpy as np

        if not matrix:
            return []
        features = np.asarray(matrix, dtype=float)
        return [int(v) for v in self.pipeline.predict(features)]

    def save(self, path: str | Path) -> None:
        """Persist the pipeline + metadata to ``path`` (parents created)."""
        import joblib

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "feature_names": self.feature_names,
                "metadata": self.metadata,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> AnomalyModel:
        """Load a model previously written by :meth:`save`."""
        import joblib

        blob = joblib.load(path)
        return cls(
            pipeline=blob["pipeline"],
            feature_names=blob["feature_names"],
            metadata=blob.get("metadata", {}),
        )
