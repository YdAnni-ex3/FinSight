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
from decimal import Decimal
from pathlib import Path

from finsight_common.categorize import categorize_by_rules
from finsight_common.ml import AnomalyModel, statement_feature_matrix
from finsight_common.models import Category, Statement, Transaction
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


# Kaggle "Credit card transactions - India" Exp Type -> our canonical categories.
_EXP_TYPE_TO_CATEGORY = {
    "Bills": Category.UTILITIES,
    "Food": Category.DINING,
    "Grocery": Category.GROCERIES,
    "Fuel": Category.TRANSPORT,
    "Entertainment": Category.ENTERTAINMENT,
    "Travel": Category.TRAVEL,
}


def _load_kaggle_india_cc(path: Path) -> list[Statement]:
    """Load the 'Credit card transactions - India' dataset into pseudo-statements.

    Real transactions are grouped by (city, month) so each group behaves like a
    single account's monthly statement -- which is what the within-statement
    feature normalization (ratios/z-scores vs. that statement) expects.
    """
    import pandas as pd

    df = pd.read_csv(path).rename(columns={"Exp Type": "ExpType", "Card Type": "CardType"})
    df["Date"] = pd.to_datetime(df["Date"], format="%d-%b-%y", errors="coerce")
    df = df.dropna(subset=["Date", "Amount"])
    df["ym"] = df["Date"].dt.to_period("M").astype(str)

    statements: list[Statement] = []
    for _, group in df.groupby(["City", "ym"]):
        transactions: list[Transaction] = []
        for row in group.itertuples(index=False):
            exp_type = str(row.ExpType)
            description = redact_text(f"{exp_type} spend {row.CardType} card {row.City}")
            category = _EXP_TYPE_TO_CATEGORY.get(exp_type) or categorize_by_rules(description)
            transactions.append(
                Transaction(
                    txn_date=row.Date.date(),
                    description=description,
                    amount=Decimal(str(-abs(int(row.Amount)))),
                    category=category,
                )
            )
        if len(transactions) >= 5:
            statements.append(Statement(transactions=transactions))
    return statements


def _load_kaggle_daily_transactions(path: Path) -> list[Statement]:
    """Load the 'Daily Household Transactions' dataset into pseudo-statements.

    Rich real-world notes/categories with an income/expense flag. Grouped by
    (payment mode, month) so each group approximates one account-month.
    """
    import pandas as pd

    df = pd.read_csv(path).rename(columns={"Income/Expense": "Flow"})
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date", "Amount"])
    df["ym"] = df["Date"].dt.to_period("M").astype(str)

    statements: list[Statement] = []
    for _, group in df.groupby(["Mode", "ym"]):
        transactions: list[Transaction] = []
        for row in group.itertuples(index=False):
            is_income = str(row.Flow).strip().lower() == "income"
            parts = [str(row.Category), str(row.Subcategory), str(row.Note)]
            joined = " ".join(p for p in parts if p and p != "nan")
            description = redact_text(joined) or "transaction"
            amount = abs(float(row.Amount))
            signed = amount if is_income else -amount
            category = Category.INCOME if is_income else categorize_by_rules(description)
            transactions.append(
                Transaction(
                    txn_date=row.Date.date(),
                    description=description,
                    amount=Decimal(str(signed)),
                    category=category,
                )
            )
        if sum(1 for t in transactions if t.amount < 0) >= 5:
            statements.append(Statement(transactions=transactions))
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
    parser.add_argument("--kaggle-csv", default=None, help="path to the India credit-card CSV")
    parser.add_argument(
        "--kaggle-daily-csv", default=None, help="path to the Daily Household Transactions CSV"
    )
    parser.add_argument("--no-mlflow", action="store_true", help="skip MLflow tracking")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    statements = _load_statements(data_dir)
    for csv_path, loader in (
        (args.kaggle_csv, _load_kaggle_india_cc),
        (args.kaggle_daily_csv, _load_kaggle_daily_transactions),
    ):
        if not csv_path:
            continue
        path = Path(csv_path)
        if path.exists():
            loaded = loader(path)
            print(f"Loaded {len(loaded)} pseudo-statements from {path.name}")
            statements += loaded
        else:
            print(f"Kaggle CSV not found: {path}")
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
