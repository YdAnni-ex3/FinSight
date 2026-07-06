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


# ── Dataset 3: Generic bank transaction CSV (fraud-detection style) ──────────
# Compatible with several Kaggle datasets that share this shape:
# TransactionID, AccountID, TransactionDate, TransactionAmount,
# TransactionType (DEBIT/CREDIT), MerchantName/Category, Location
_GENERIC_TYPE_TO_SIGNED: dict[str, int] = {
    "debit": -1,
    "credit": 1,
    "withdrawal": -1,
    "deposit": 1,
    "payment": -1,
    "transfer_out": -1,
    "transfer_in": 1,
    "purchase": -1,
    "refund": 1,
}


def _load_generic_bank_transactions(path: Path) -> list[Statement]:
    """Load a generic bank-transaction CSV with amount + debit/credit type.

    Tries to auto-detect the relevant columns by name (case-insensitive), so it
    works with a broad family of Kaggle fraud-detection datasets.
    """
    import pandas as pd

    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Detect date column
    date_col = next(
        (c for c in df.columns if "date" in c or "time" in c or "timestamp" in c),
        None,
    )
    # Detect amount column
    amount_col = next(
        (c for c in df.columns if "amount" in c or "value" in c),
        None,
    )
    if not amount_col or not date_col:
        print(f"  Skipping {path.name}: cannot detect date/amount columns ({list(df.columns[:8])})")
        return []

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, amount_col])
    df["_amount"] = pd.to_numeric(df[amount_col], errors="coerce").abs()
    df = df.dropna(subset=["_amount"])
    df["ym"] = df[date_col].dt.to_period("M").astype(str)

    # Detect transaction type column
    type_col = next(
        (c for c in df.columns if "type" in c or "transaction_type" in c or "direction" in c),
        None,
    )
    # Detect description column
    desc_col = next(
        (
            c
            for c in df.columns
            if any(k in c for k in ("merchant", "description", "category", "narration", "name", "detail"))
        ),
        None,
    )

    group_cols = [c for c in ("account_id", "accountid", "account", "customerid") if c in df.columns]
    group_by = (group_cols[:1] or []) + ["ym"]

    statements: list[Statement] = []
    for _, group in df.groupby(group_by):
        transactions: list[Transaction] = []
        for row in group.itertuples(index=False):
            amount = float(getattr(row, "_amount"))
            # Determine sign from type column
            sign = -1  # default: expense
            if type_col:
                raw_type = str(getattr(row, type_col, "")).strip().lower()
                sign = _GENERIC_TYPE_TO_SIGNED.get(raw_type, -1)
            signed = Decimal(str(sign * amount))
            description = "transaction"
            if desc_col:
                raw_desc = str(getattr(row, desc_col, ""))
                if raw_desc and raw_desc.lower() != "nan":
                    description = redact_text(raw_desc[:100])
            category = categorize_by_rules(description)
            try:
                txn_date = getattr(row, date_col).date()
            except Exception:
                from datetime import date

                txn_date = date.today()
            transactions.append(
                Transaction(
                    txn_date=txn_date,
                    description=description,
                    amount=signed,
                    category=category,
                )
            )
        outflows = sum(1 for t in transactions if t.amount < 0)
        if outflows >= 5:
            statements.append(Statement(transactions=transactions))
    return statements


# ── Dataset 4: Personal Finance Transactions (rajatrc1705 or similar) ─────────
# Format: Date, Category, Amount, Income/Expense, Note
def _load_personal_finance_transactions(path: Path) -> list[Statement]:
    """Load a personal-finance CSV with Category, Amount and Income/Expense flag.

    Works with several Kaggle personal-finance datasets (e.g. rajatrc1705's).
    Columns matched case-insensitively; rows grouped by month.
    """
    import pandas as pd

    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    date_col = next((c for c in df.columns if "date" in c), None)
    amount_col = next((c for c in df.columns if "amount" in c), None)
    flow_col = next((c for c in df.columns if "income" in c or "expense" in c or "type" in c), None)
    cat_col = next((c for c in df.columns if "categor" in c), None)

    if not amount_col:
        print(f"  Skipping {path.name}: no amount column found")
        return []

    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
        df = df.dropna(subset=[date_col])
        df["ym"] = df[date_col].dt.to_period("M").astype(str)
    else:
        df["ym"] = "unknown"

    df["_amount"] = pd.to_numeric(df[amount_col], errors="coerce").abs()
    df = df.dropna(subset=["_amount"])

    statements: list[Statement] = []
    for ym, group in df.groupby("ym"):
        transactions: list[Transaction] = []
        for row in group.itertuples(index=False):
            amount = float(row._amount)
            is_income = False
            if flow_col:
                raw_flow = str(getattr(row, flow_col, "")).strip().lower()
                is_income = "income" in raw_flow or raw_flow in ("credit", "in", "+")
            signed = Decimal(str(amount if is_income else -amount))

            parts: list[str] = []
            if cat_col:
                parts.append(str(getattr(row, cat_col, "") or ""))
            for extra_col in ("note", "description", "narration", "subcategory"):
                if extra_col in df.columns:
                    val = str(getattr(row, extra_col, "") or "")
                    if val and val.lower() != "nan":
                        parts.append(val)
            description = redact_text(" ".join(p for p in parts if p).strip()[:100]) or "transaction"
            category = Category.INCOME if is_income else categorize_by_rules(description)

            import datetime

            txn_date = (
                getattr(row, date_col).date()
                if date_col and hasattr(getattr(row, date_col, None), "date")
                else datetime.date.today()
            )
            transactions.append(
                Transaction(
                    txn_date=txn_date,
                    description=description,
                    amount=signed,
                    category=category,
                )
            )
        outflows = sum(1 for t in transactions if t.amount < 0)
        if outflows >= 3:
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
    parser.add_argument("--kaggle-generic-csv", default=None, help="path to a generic bank-transaction CSV")
    parser.add_argument(
        "--kaggle-personal-csv", default=None, help="path to a personal-finance transactions CSV"
    )
    parser.add_argument("--no-mlflow", action="store_true", help="skip MLflow tracking")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    statements = _load_statements(data_dir)
    for csv_path, loader in (
        (args.kaggle_csv, _load_kaggle_india_cc),
        (args.kaggle_daily_csv, _load_kaggle_daily_transactions),
        (args.kaggle_generic_csv, _load_generic_bank_transactions),
        (args.kaggle_personal_csv, _load_personal_finance_transactions),
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
