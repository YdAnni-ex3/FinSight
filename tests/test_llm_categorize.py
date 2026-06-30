from finsight_common.llm_categorize import llm_categorize
from finsight_common.models import Category


class FakeProvider:
    """A stand-in LLM provider that returns a canned chat response."""

    name = "fake"

    def __init__(self, response: str):
        self._response = response
        self.calls: list = []

    def chat(self, messages, *, temperature: float = 0.0) -> str:
        self.calls.append(messages)
        return self._response

    def embed(self, texts):
        return [[0.0] for _ in texts]


def test_maps_valid_json():
    provider = FakeProvider('["dining", "income"]')
    assert llm_categorize(["Swiggy order", "Salary"], provider) == [
        Category.DINING,
        Category.INCOME,
    ]


def test_handles_code_fences():
    provider = FakeProvider('```json\n["groceries"]\n```')
    assert llm_categorize(["BigBasket"], provider) == [Category.GROCERIES]


def test_prose_around_array_is_tolerated():
    provider = FakeProvider('Sure! Here you go: ["transport"] — hope that helps')
    assert llm_categorize(["Uber ride"], provider) == [Category.TRANSPORT]


def test_invalid_category_falls_back_to_rules_per_item():
    provider = FakeProvider('["dining", "not-a-category"]')
    cats = llm_categorize(["Swiggy order", "Netflix subscription"], provider)
    assert cats[0] == Category.DINING
    assert cats[1] == Category.SUBSCRIPTIONS  # filled in by the rules engine


def test_provider_error_falls_back_to_rules():
    class Boom:
        name = "boom"

        def chat(self, messages, *, temperature: float = 0.0) -> str:
            raise RuntimeError("no provider configured")

        def embed(self, texts):
            raise RuntimeError

    assert llm_categorize(["Uber ride"], Boom()) == [Category.TRANSPORT]


def test_empty_input():
    assert llm_categorize([], FakeProvider("[]")) == []
