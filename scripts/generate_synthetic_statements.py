"""Generate synthetic bank statements for local development and demos.

No cloud or Kaggle access required. Produces CSV (always), XLSX (if openpyxl is
available), and PDF (if reportlab is available) into ``data/synthetic/``. Some
descriptions intentionally embed PII (emails, phone numbers, PAN) so the
redaction pass has something to catch, and a few rows are deliberate anomalies
(duplicate large charges) for the anomaly module later.

Usage:
    python scripts/generate_synthetic_statements.py --count 5
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

# (description template, min, max, is_credit)
_PATTERNS: list[tuple[str, int, int, bool]] = [
    ("Salary credit ACME CORP PAN ABCDE1234F", 40000, 90000, True),
    ("UPI to ramesh@okhdfcbank 9876543210", 100, 5000, False),
    ("Swiggy order Koramangala", 150, 900, False),
    ("Zomato dinner", 200, 1200, False),
    ("BigBasket groceries", 500, 3000, False),
    ("Amazon.in purchase", 300, 8000, False),
    ("Uber ride", 80, 700, False),
    ("Netflix subscription", 199, 799, False),
    ("Airtel broadband bill", 499, 1499, False),
    ("Apollo Pharmacy", 100, 2500, False),
    ("IRCTC train ticket", 250, 3500, False),
    ("Electricity bill BESCOM", 600, 4000, False),
    ("ATM withdrawal", 1000, 10000, False),
    ("Interest credit", 50, 800, True),
]

# Anomalies: unusually large, duplicated charges.
_ANOMALIES: list[tuple[str, int]] = [
    ("Online electronics megastore", 65000),
    ("Online electronics megastore", 65000),
]


def _random_statement(seed: int, months_back: int = 1) -> list[dict]:
    rng = random.Random(seed)
    start = date.today().replace(day=1) - timedelta(days=30 * months_back)
    balance = rng.randint(20000, 60000)
    rows: list[dict] = []

    n = rng.randint(25, 40)
    for _ in range(n):
        template, lo, hi, is_credit = rng.choice(_PATTERNS)
        amount = rng.randint(lo, hi)
        debit = 0 if is_credit else amount
        credit = amount if is_credit else 0
        balance += credit - debit
        rows.append(
            {
                "Date": (start + timedelta(days=rng.randint(0, 27))).isoformat(),
                "Description": template,
                "Debit": debit or "",
                "Credit": credit or "",
                "Balance": balance,
            }
        )

    for desc, amount in _ANOMALIES:
        balance -= amount
        rows.append(
            {
                "Date": (start + timedelta(days=rng.randint(0, 27))).isoformat(),
                "Description": desc,
                "Debit": amount,
                "Credit": "",
                "Balance": balance,
            }
        )

    rows.sort(key=lambda r: r["Date"])
    return rows


def _write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["Date", "Description", "Debit", "Credit", "Balance"]
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_xlsx(rows: list[dict], path: Path) -> bool:
    try:
        from openpyxl import Workbook
    except ImportError:
        return False
    wb = Workbook()
    ws = wb.active
    ws.append(["Date", "Description", "Debit", "Credit", "Balance"])
    for r in rows:
        ws.append([r["Date"], r["Description"], r["Debit"], r["Credit"], r["Balance"]])
    wb.save(path)
    return True


def _write_pdf(rows: list[dict], path: Path) -> bool:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    except ImportError:
        return False
    data = [["Date", "Description", "Debit", "Credit", "Balance"]]
    data += [[r["Date"], r["Description"], r["Debit"], r["Credit"], r["Balance"]] for r in rows]
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
            ]
        )
    )
    doc.build([table])
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic FinSight statements")
    parser.add_argument("--count", type=int, default=5, help="number of statements to generate")
    parser.add_argument("--out", type=Path, default=Path("data/synthetic"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    wrote_xlsx = wrote_pdf = False

    for i in range(args.count):
        rows = _random_statement(seed=1000 + i)
        stem = args.out / f"statement_{i + 1:02d}"
        _write_csv(rows, stem.with_suffix(".csv"))
        wrote_xlsx = _write_xlsx(rows, stem.with_suffix(".xlsx")) or wrote_xlsx
        wrote_pdf = _write_pdf(rows, stem.with_suffix(".pdf")) or wrote_pdf

    print(
        f"Wrote {args.count} statement(s) to {args.out}/ (csv"
        + (", xlsx" if wrote_xlsx else "")
        + (", pdf" if wrote_pdf else "")
        + ")"
    )
    if not wrote_xlsx or not wrote_pdf:
        print("Tip: install the 'data' extra for XLSX/PDF output: uv sync --extra data")


if __name__ == "__main__":
    main()
