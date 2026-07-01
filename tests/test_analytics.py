from datetime import date
from decimal import Decimal

from finsight_common.analytics import spend_by_category
from finsight_common.models import Category, Statement, Transaction


def _txn(amount, category, day=1):
    return Transaction(
        txn_date=date(2024, 3, day), description="x", amount=Decimal(str(amount)), category=category
    )


def test_spend_by_category_sums_and_sorts_outflows():
    statement = Statement(
        transactions=[
            _txn(-450, Category.DINING),
            _txn(-550, Category.DINING),
            _txn(-1200, Category.RENT),
            _txn(50000, Category.INCOME),  # inflow ignored
        ]
    )
    result = spend_by_category(statement)
    assert list(result.keys()) == ["rent", "dining"]
    assert result == {"rent": 1200.0, "dining": 1000.0}


def test_spend_by_category_empty():
    assert spend_by_category(Statement(transactions=[])) == {}
