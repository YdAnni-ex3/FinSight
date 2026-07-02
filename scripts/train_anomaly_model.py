"""Train the FinSight anomaly model (IsolationForest) and track it in MLflow.

Offline and account-free: reads the synthetic statements, applies the same
PII-redaction + rule-categorization the API applies at request time, engineers
user-relative features, fits an IsolationForest, and logs params/metrics/model
to a *local* MLflow tracking store (./mlruns). The fitted model is also saved to
``models/`` so the gateway can load and serve it.

Examples
--------
    python -m uv run python scripts/train_anomaly_model.py
    python -m uv run python scripts/train_anomaly_model.py --contamination 0.05
    python -m uv run mlflow ui --backend-store-uri sqlite:///mlflow.db  # open :5000
"""

from __future__ import annotations

import argparse
from pathlib import Path

from finsight_common.categorize import categorize_by_rules
from finsight_common.ml import AnomalyModel, statement_feature_matrix
from finsight_common.models import Statement
from finsight_common.parsing import parse_bytes
from finsight_common.pii import redact_text

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_statements(data_dir: Path) -> list[Statement]:
    statements: list[Statement] = []
    for path in sorted(data_dir.glob("*.csv")):
        statement = parse_bytes(path.read_bytes(), path.name)
        for txn in statement.transactions:
            txn.description = redact_text(txn.description)
            txn.category = categorize_by_rules(txn.description)
        statements.append(statement)
    return statements


def _build_matrix(statements: list[Statement]) -> list[list[float]]:
    matrix: list[list[float]] = []
    for statement in statements:
        rows, _ = statement_feature_matrix(statement)
        matrix.extend(rows)
    return matrix


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the FinSight anomaly model")
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "data" / "synthetic"))
    parser.add_argument("--out", default=str(REPO_ROOT / "models" / "anomaly_isoforest.joblib"))
    parser.add_argument("--contamination", type=float, default=0.03)
    parser.add_argument("--n-estimators", type=int, default=150)
    parser.add_argument("--no-mlflow", action="store_true", help="skip MLflow tracking")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    statements = _load_statements(data_dir)
    if not statements:
        raise SystemExit(
            f"No statements found in {data_dir}. Run: "
            "python -m uv run python scripts/generate_synthetic_statements.py --count 5"
        )

    matrix = _build_matrix(statements)
    print(f"Loaded {len(statements)} statements -> {len(matrix)} outflow transactions")

    model = AnomalyModel.fit(
        matrix,
        contamination=args.contamination,
        n_estimators=args.n_estimators,
        metadata={"n_statements": len(statements)},
    )

    predictions = model.predict(matrix)
    scores = model.decision_scores(matrix)
    n_outliers = sum(1 for p in predictions if p == -1)
    metrics = {
        "n_outliers": float(n_outliers),
        "outlier_rate": n_outliers / len(matrix),
        "score_mean": sum(scores) / len(scores),
        "score_min": min(scores),
    }

    model.save(args.out)
    print(f"Saved model -> {args.out}")
    print(f"Metrics: {metrics}")

    if args.no_mlflow:
        return

    try:
        import mlflow
        import mlflow.sklearn
    except ImportError:
        print("mlflow not installed (pip install '.[mlops]') - skipping tracking")
        return

    # MLflow 3.x deprecated the bare file store; use a local SQLite backend.
    db_path = (REPO_ROOT / "mlflow.db").as_posix()
    mlflow.set_tracking_uri(f"sqlite:///{db_path}")
    mlflow.set_experiment("finsight-anomaly")
    with mlflow.start_run():
        mlflow.log_params(
            {
                "contamination": args.contamination,
                "n_estimators": args.n_estimators,
                "n_samples": model.metadata["n_samples"],
                "n_features": model.metadata["n_features"],
                "n_statements": len(statements),
                "features": ",".join(model.feature_names),
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(
            model.pipeline,
            name="model",
            pip_requirements=["scikit-learn", "numpy", "joblib"],
        )
        mlflow.log_artifact(args.out, artifact_path="joblib")
    print("Logged run to MLflow -> sqlite:///mlflow.db  (view: python -m uv run mlflow ui)")


if __name__ == "__main__":
    main()
