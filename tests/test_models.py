from datetime import date
from decimal import Decimal

from finsight_common.models import Category, Statement, Transaction


def test_amount_serializes_to_float():
    txn = Transaction(txn_date=date(2024, 3, 1), description="Salary", amount=Decimal("50000.50"))
    dumped = txn.model_dump(mode="json")
    assert dumped["amount"] == 50000.5
    assert isinstance(dumped["amount"], float)


def test_balance_none_serializes_to_none():
    txn = Transaction(txn_date=date(2024, 3, 1), description="x", amount=Decimal("-10"))
    assert txn.model_dump(mode="json")["balance"] is None
    assert txn.is_outflow is True


def test_statement_totals():
    statement = Statement(
        transactions=[
            Transaction(txn_date=date(2024, 3, 1), description="Salary", amount=Decimal("50000")),
            Transaction(txn_date=date(2024, 3, 2), description="Rent", amount=Decimal("-15000")),
            Transaction(txn_date=date(2024, 3, 3), description="Food", amount=Decimal("-500")),
        ]
    )
    assert statement.total_inflow == Decimal("50000")
    assert statement.total_outflow == Decimal("15500")
    assert statement.net == Decimal("34500")


def test_category_enum_values():
    assert Category.GROCERIES.value == "groceries"
    assert Category("dining") is Category.DINING
