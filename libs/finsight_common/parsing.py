"""Statement parsing: CSV / XLSX / PDF bytes -> :class:`Statement`.

Heavy parsers (pandas, pdfplumber) are imported lazily so the core package
stays light. Column names are normalized and mapped from common bank-statement
synonyms; separate debit/credit columns are merged into a single signed
``amount`` (positive = inflow, negative = outflow).
"""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import Statement, Transaction

_DATE_ALIASES = {"date", "txn date", "transaction date", "value date", "posting date"}
_DESC_ALIASES = {"description", "narration", "details", "particulars", "remarks"}
_AMOUNT_ALIASES = {"amount", "amount (inr)", "txn amount", "transaction amount"}
_DEBIT_ALIASES = {"debit", "withdrawal", "withdrawal amt", "dr"}
_CREDIT_ALIASES = {"credit", "deposit", "deposit amt", "cr"}
_BALANCE_ALIASES = {"balance", "closing balance", "available balance", "running balance"}

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%d %b %Y")


class StatementParseError(ValueError):
    """Raised when a statement file cannot be parsed."""


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("\u20b9", "")
    if text in ("", "-", "nan", "None"):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise StatementParseError(f"Unrecognized date format: {value!r}")


def _match(columns: dict[str, str], aliases: set[str]) -> str | None:
    for norm, original in columns.items():
        if norm in aliases:
            return original
    return None


def parse_file(path: str | Path) -> Statement:
    """Parse a statement file from disk, dispatching on extension."""
    path = Path(path)
    return parse_bytes(path.read_bytes(), path.name)


def parse_bytes(data: bytes, filename: str) -> Statement:
    """Parse statement ``data`` given its ``filename`` (used for the extension)."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        rows = _read_tabular(data, kind="csv")
    elif suffix in (".xlsx", ".xls"):
        rows = _read_tabular(data, kind="excel")
    elif suffix == ".pdf":
        rows = _read_pdf(data)
    else:
        raise StatementParseError(f"Unsupported file type: {suffix or filename!r}")

    transactions = _rows_to_transactions(rows)
    statement = Statement(source_filename=filename, transactions=transactions)
    if transactions:
        statement.period_start = min(t.txn_date for t in transactions)
        statement.period_end = max(t.txn_date for t in transactions)
    return statement


def _read_tabular(data: bytes, *, kind: str) -> list[dict]:
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise StatementParseError("Install the 'data' extra to parse CSV/XLSX files") from exc

    buffer = io.BytesIO(data)
    df = pd.read_csv(buffer) if kind == "csv" else pd.read_excel(buffer, engine="openpyxl")
    df = df.where(df.notna(), None)
    return df.to_dict(orient="records")


def _read_pdf(data: bytes) -> list[dict]:  # pragma: no cover - best-effort, table-layout dependent
    try:
        import pdfplumber
    except ImportError as exc:
        raise StatementParseError("Install the 'data' extra to parse PDF files") from exc

    rows: list[dict] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table or len(table) < 2:
                continue
            header = [(h or "").strip() for h in table[0]]
            for record in table[1:]:
                rows.append(dict(zip(header, record, strict=False)))
    return rows


def _rows_to_transactions(rows: list[dict]) -> list[Transaction]:
    if not rows:
        return []

    columns = {str(k).strip().lower(): k for k in rows[0]}
    date_col = _match(columns, _DATE_ALIASES)
    desc_col = _match(columns, _DESC_ALIASES)
    amount_col = _match(columns, _AMOUNT_ALIASES)
    debit_col = _match(columns, _DEBIT_ALIASES)
    credit_col = _match(columns, _CREDIT_ALIASES)
    balance_col = _match(columns, _BALANCE_ALIASES)

    if not date_col or not desc_col:
        raise StatementParseError("Statement is missing required date/description columns")

    transactions: list[Transaction] = []
    for row in rows:
        if row.get(date_col) in (None, ""):
            continue

        if amount_col is not None:
            amount = _to_decimal(row.get(amount_col)) or Decimal("0")
        else:
            debit = _to_decimal(row.get(debit_col)) if debit_col else None
            credit = _to_decimal(row.get(credit_col)) if credit_col else None
            amount = (credit or Decimal("0")) - (debit or Decimal("0"))

        transactions.append(
            Transaction(
                txn_date=_to_date(row[date_col]),
                description=str(row.get(desc_col, "")).strip(),
                amount=amount,
                balance=_to_decimal(row.get(balance_col)) if balance_col else None,
            )
        )
    return transactions
