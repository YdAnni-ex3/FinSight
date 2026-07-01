from datetime import date
from decimal import Decimal

from finsight_common.anomaly import detect_anomalies
from finsight_common.models import Statement, Transaction


def _txn(desc: str, amount, day: int = 1) -> Transaction:
    return Transaction(txn_date=date(2024, 3, day), description=desc, amount=Decimal(str(amount)))


def test_flags_large_transaction():
    txns = [_txn("Coffee", -100, i) for i in range(1, 6)] + [_txn("TV megastore", -65000, 10)]
    anomalies = detect_anomalies(Statement(transactions=txns))
    large = [a for a in anomalies if a.type == "large_transaction"]
    assert len(large) == 1
    assert large[0].severity == "high"
    assert large[0].transactions[0]["amount"] == -65000.0


def test_flags_possible_duplicate():
    txns = [_txn("Rent", -15000, 1), _txn("Rent", -15000, 1), _txn("Coffee", -100, 2)]
    anomalies = detect_anomalies(Statement(transactions=txns))
    dupes = [a for a in anomalies if a.type == "possible_duplicate"]
    assert len(dupes) == 1
    assert len(dupes[0].transactions) == 2


def test_clean_statement_has_no_large_flags():
    txns = [_txn(f"Shop {i}", -(100 + i), i) for i in range(1, 8)]
    anomalies = detect_anomalies(Statement(transactions=txns))
    assert all(a.type != "large_transaction" for a in anomalies)


def test_inflows_are_ignored():
    txns = [_txn("Salary", 500000, 1)] + [_txn(f"Coffee {i}", -100, i) for i in range(2, 6)]
    anomalies = detect_anomalies(Statement(transactions=txns))
    assert anomalies == []
