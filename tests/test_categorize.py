from finsight_common.categorize import categorize_by_rules
from finsight_common.models import Category


def test_known_merchants_map_to_categories():
    assert categorize_by_rules("Swiggy order Koramangala") is Category.DINING
    assert categorize_by_rules("Netflix subscription") is Category.SUBSCRIPTIONS
    assert categorize_by_rules("Salary credit ACME") is Category.INCOME
    assert categorize_by_rules("Uber ride home") is Category.TRANSPORT
    assert categorize_by_rules("BigBasket groceries") is Category.GROCERIES


def test_unknown_falls_back_to_other():
    assert categorize_by_rules("Mysterious payee xyz") is Category.OTHER
