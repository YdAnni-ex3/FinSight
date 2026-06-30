from decimal import Decimal

import pytest

pytest.importorskip("pandas")

from finsight_common.parsing import StatementParseError, parse_bytes  # noqa: E402

_CSV = b"""Date,Description,Debit,Credit,Balance
2024-03-01,Salary Acme Corp,,50000,50000
2024-03-02,Swiggy order,450,,49550
2024-03-05,ATM withdrawal,2000,,47550
"""


def test_parses_debit_credit_into_signed_amount():
    statement = parse_bytes(_CSV, "march.csv")
    assert len(statement.transactions) == 3

    salary, swiggy, atm = statement.transactions
    assert salary.amount == Decimal("50000")
    assert swiggy.amount == Decimal("-450")
    assert atm.amount == Decimal("-2000")
    assert statement.period_start.isoformat() == "2024-03-01"
    assert statement.period_end.isoformat() == "2024-03-05"


def test_single_amount_column():
    csv = b"Date,Description,Amount\n01-03-2024,Refund,1200\n02-03-2024,Coffee,-150\n"
    statement = parse_bytes(csv, "amt.csv")
    assert statement.transactions[0].amount == Decimal("1200")
    assert statement.transactions[1].amount == Decimal("-150")


def test_unsupported_extension():
    with pytest.raises(StatementParseError):
        parse_bytes(b"x", "notes.txt")


def test_missing_required_columns():
    with pytest.raises(StatementParseError):
        parse_bytes(b"Foo,Bar\n1,2\n", "bad.csv")
