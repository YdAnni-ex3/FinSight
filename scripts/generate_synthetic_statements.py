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
    # ── Income ──────────────────────────────────────────────────────────────
    ("Salary credit ACME CORP PAN ABCDE1234F", 40000, 120000, True),
    ("Freelance payment from client XYZ", 8000, 40000, True),
    ("UPI received 9876543210 transfer", 500, 15000, True),
    ("Interest credit savings account", 50, 2500, True),
    ("Dividend credit NIFTY50 holdings", 200, 5000, True),
    ("Refund Amazon.in order", 200, 4000, True),
    ("GST refund credit IT dept", 500, 8000, True),
    # ── Food & Dining ────────────────────────────────────────────────────────
    ("Swiggy order Koramangala Bengaluru", 150, 900, False),
    ("Zomato dinner order Mumbai", 200, 1200, False),
    ("Dominos Pizza order", 199, 799, False),
    ("McDonald's outlet Indiranagar", 120, 600, False),
    ("Starbucks Coffee South Ex", 200, 800, False),
    ("MTR Foods lunch", 80, 350, False),
    ("KFC outlet Connaught Place", 200, 900, False),
    ("Cafe Coffee Day Bandra", 150, 600, False),
    ("Local dhaba meal", 60, 300, False),
    ("Barbeque Nation dinner", 800, 2500, False),
    ("Restaurant bill food+drinks", 400, 3500, False),
    # ── Groceries ────────────────────────────────────────────────────────────
    ("BigBasket monthly groceries", 500, 4000, False),
    ("Blinkit express groceries", 200, 1500, False),
    ("Zepto groceries delivery", 150, 1200, False),
    ("Reliance Fresh supermarket", 300, 3000, False),
    ("D-Mart monthly household", 800, 6000, False),
    ("Spencer's Retail grocery", 400, 2500, False),
    ("More Supermarket vegetables", 200, 1500, False),
    # ── Transport ────────────────────────────────────────────────────────────
    ("Uber ride Bengaluru", 80, 700, False),
    ("Ola cab Mumbai airport", 200, 1200, False),
    ("Rapido bike taxi", 30, 200, False),
    ("Indian Oil petrol fill", 500, 3000, False),
    ("HPCL fuel station", 400, 2500, False),
    ("BMTC monthly pass", 400, 600, False),
    ("Delhi Metro smart card recharge", 200, 1000, False),
    ("FastTag highway toll", 50, 600, False),
    ("IndiGo flight booking DEL-BOM", 2500, 12000, False),
    ("Air India ticket booking", 3000, 18000, False),
    ("RedBus bus ticket booking", 300, 2000, False),
    # ── Entertainment ────────────────────────────────────────────────────────
    ("Netflix subscription monthly", 199, 649, False),
    ("Amazon Prime membership", 179, 999, False),
    ("Spotify Premium subscription", 59, 179, False),
    ("PVR Cinemas movie tickets", 300, 1200, False),
    ("BookMyShow event tickets", 400, 2500, False),
    ("Hotstar subscription", 299, 899, False),
    ("Sony LIV subscription", 299, 799, False),
    ("Gaming subscription Xbox/PS", 400, 800, False),
    # ── Utilities & Bills ────────────────────────────────────────────────────
    ("Electricity bill BESCOM Bengaluru", 600, 4000, False),
    ("BSES electricity bill Delhi", 500, 3500, False),
    ("Airtel broadband monthly bill", 499, 1499, False),
    ("Jio postpaid mobile bill", 349, 999, False),
    ("BSNL landline bill", 200, 800, False),
    ("Piped gas bill AGGL", 200, 1200, False),
    ("Water supply tax BBMP", 100, 600, False),
    ("Society maintenance charge", 1500, 5000, False),
    ("House rent transfer NEFT", 8000, 35000, False),
    # ── Shopping ────────────────────────────────────────────────────────────
    ("Amazon.in purchase electronics", 300, 12000, False),
    ("Flipkart order clothing", 400, 5000, False),
    ("Myntra fashion order", 500, 4000, False),
    ("Ajio apparel purchase", 300, 3000, False),
    ("Nykaa beauty products", 200, 2500, False),
    ("Croma electronics store", 1500, 25000, False),
    ("Vijay Sales appliance purchase", 2000, 35000, False),
    ("Tata Cliq order", 500, 8000, False),
    ("Meesho online order", 200, 2000, False),
    # ── Healthcare ────────────────────────────────────────────────────────────
    ("Apollo Pharmacy medicines", 100, 2500, False),
    ("Medplus pharmacy", 150, 2000, False),
    ("Columbia Asia hospital consultation", 500, 3000, False),
    ("Fortis hospital bill", 2000, 15000, False),
    ("Pathology lab blood test", 300, 2500, False),
    ("Dental clinic treatment", 500, 8000, False),
    ("Eyecare clinic consultation", 300, 2000, False),
    ("PharmEasy medicine delivery", 200, 1500, False),
    # ── Travel ────────────────────────────────────────────────────────────────
    ("MakeMyTrip hotel booking Goa", 2000, 12000, False),
    ("OYO Rooms stay Chennai", 800, 4000, False),
    ("Airbnb stay Coorg weekend", 1500, 8000, False),
    ("IRCTC train ticket Rajdhani", 250, 3500, False),
    ("Goibibo flight hotel combo", 3000, 20000, False),
    ("Yatra travel booking", 2500, 15000, False),
    # ── Financial ────────────────────────────────────────────────────────────
    ("LIC premium payment", 2000, 15000, False),
    ("HDFC Life insurance premium", 3000, 20000, False),
    ("SIP mutual fund Zerodha", 1000, 10000, False),
    ("NPS contribution tier 1", 500, 5000, False),
    ("Home loan EMI HDFC Bank", 8000, 45000, False),
    ("Car loan EMI ICICI Bank", 5000, 20000, False),
    ("Credit card bill payment Axis", 2000, 30000, False),
    ("ATM cash withdrawal", 1000, 15000, False),
]

# Anomaly patterns: (description, amount, is_duplicate)
_ANOMALIES: list[tuple[str, int, bool]] = [
    ("Online electronics megastore large purchase", 75000, False),
    ("Online electronics megastore large purchase", 75000, True),  # duplicate
    ("Overseas wire transfer suspicious", 95000, False),
    ("ATM withdrawal midnight", 20000, False),
    ("Unknown merchant foreign transaction", 45000, False),
    ("Luxury item purchase jewelry", 120000, False),
]


def _random_statement(seed: int, months_back: int = 1, add_anomalies: bool = True) -> list[dict]:
    rng = random.Random(seed)
    start = date.today().replace(day=1) - timedelta(days=30 * months_back)
    # Vary income level: low, medium, high earner
    income_tier = rng.choice(["low", "medium", "high"])
    base_balance = {"low": rng.randint(5000, 20000), "medium": rng.randint(20000, 80000), "high": rng.randint(80000, 300000)}[income_tier]
    balance = base_balance
    rows: list[dict] = []

    # More transactions for richer profiles
    n = {"low": rng.randint(15, 30), "medium": rng.randint(30, 55), "high": rng.randint(45, 80)}[income_tier]
    for _ in range(n):
        template, lo, hi, is_credit = rng.choice(_PATTERNS)
        # Scale amounts with income tier
        scale = {"low": 0.5, "medium": 1.0, "high": 2.5}[income_tier]
        amount = int(rng.randint(lo, hi) * scale)
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

    # Inject a random subset of anomalies (not always both)
    if add_anomalies:
        # Pick 1-2 anomalies at random, skipping duplicates if already used
        seen_descs: set[str] = set()
        anomaly_pool = list(_ANOMALIES)
        rng.shuffle(anomaly_pool)
        injected = 0
        for desc, base_amount, is_dup in anomaly_pool:
            if injected >= rng.randint(1, 3):
                break
            if is_dup and desc in seen_descs:
                pass  # allow duplicate
            elif not is_dup and desc in seen_descs:
                continue
            seen_descs.add(desc)
            amount = int(base_amount * {"low": 0.5, "medium": 1.0, "high": 1.8}[income_tier])
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
            injected += 1

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
        rows = _random_statement(seed=1000 + i, add_anomalies=(i % 3 == 0))
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
