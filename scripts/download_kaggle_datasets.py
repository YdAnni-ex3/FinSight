"""Download additional Kaggle datasets for anomaly-model training.

Prerequisites
-------------
1. Install the Kaggle CLI:  ``pip install kaggle``
2. Place ``~/.kaggle/kaggle.json`` (downloaded from kaggle.com > Account > API)
   or set ``KAGGLE_USERNAME`` / ``KAGGLE_KEY`` env vars.

Usage
-----
    python scripts/download_kaggle_datasets.py
    python scripts/download_kaggle_datasets.py --out data/kaggle --datasets 1 2 3 4

Then retrain with all datasets::

    python scripts/train_anomaly_model.py \\
        --kaggle-csv "data/kaggle/Credit card transactions - India - Simple.csv" \\
        --kaggle-daily-csv "data/kaggle/Daily Household Transactions.csv" \\
        --kaggle-generic-csv "data/kaggle/bank_transactions/transactions.csv" \\
        --kaggle-personal-csv "data/kaggle/personal_transactions/Personal Transactions.csv"
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# dataset_id, subfolder, description
DATASETS: list[tuple[int, str, str, str]] = [
    (
        1,
        "rishikeshkonapure/zomato",
        "zomato",
        "Zomato restaurant orders — dining spend patterns",
    ),
    (
        2,
        "computingcorner/bank-transaction-dataset-for-fraud-detection",
        "bank_transactions",
        "Bank transaction dataset for fraud detection (generic format)",
    ),
    (
        3,
        "rajatrc1705/personal-finance-transactions",
        "personal_transactions",
        "Personal finance transactions (monthly household budget)",
    ),
    (
        4,
        "mlg-ulb/creditcardfraud",
        "creditcardfraud",
        "Credit card fraud detection (284k transactions, Amount + anonymised features)",
    ),
    (
        5,
        "shivamb/bank-customer-transaction-data",
        "bank_customer_transactions",
        "Bank customer transaction data (deposits / withdrawals)",
    ),
]


def _run(cmd: list[str]) -> int:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Kaggle training datasets")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "kaggle")
    parser.add_argument(
        "--datasets",
        nargs="*",
        type=int,
        help="Which dataset numbers to download (default: all). E.g. --datasets 2 3",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    # Verify kaggle CLI is available
    result = subprocess.run(["kaggle", "--version"], capture_output=True)
    if result.returncode != 0:
        print("ERROR: kaggle CLI not found. Install it: pip install kaggle")
        print("Then create ~/.kaggle/kaggle.json from kaggle.com > Account > API > Create Token")
        sys.exit(1)

    selected = set(args.datasets) if args.datasets else {d[0] for d in DATASETS}

    for num, dataset_id, subfolder, description in DATASETS:
        if num not in selected:
            continue
        dest = args.out / subfolder
        dest.mkdir(parents=True, exist_ok=True)
        print(f"\n[{num}] Downloading: {description}")
        print(f"    Dataset: {dataset_id}  →  {dest}")
        rc = _run(["kaggle", "datasets", "download", "-d", dataset_id, "-p", str(dest), "--unzip"])
        if rc != 0:
            print(f"  WARNING: Download failed for {dataset_id} (exit code {rc}). Skipping.")

    print("\n\nAll downloads finished. Run training with:")
    print(
        "  python scripts/train_anomaly_model.py \\\n"
        '    --kaggle-csv "data/kaggle/Credit card transactions - India - Simple.csv" \\\n'
        '    --kaggle-daily-csv "data/kaggle/Daily Household Transactions.csv" \\\n'
        '    --kaggle-generic-csv "data/kaggle/bank_transactions/transactions.csv" \\\n'
        '    --kaggle-personal-csv "data/kaggle/personal_transactions/Personal Transactions.csv"'
    )


if __name__ == "__main__":
    main()
