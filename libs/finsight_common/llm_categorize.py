"""LLM-backed transaction categorization.

Sends (already PII-redacted) descriptions to the configured LLM provider and
maps each to a :class:`Category`. Falls back to the deterministic rules engine
per item when the model returns something unexpected, and for the whole batch
if the call fails — so enabling an LLM only ever improves results, it never
breaks the pipeline.
"""

from __future__ import annotations

import json
import re

from .categorize import categorize_by_rules
from .llm.base import ChatMessage, LLMProvider
from .models import Category

_VALID = {c.value for c in Category}

_SYSTEM = (
    "You are a precise financial transaction classifier. "
    "Classify each bank-statement line into exactly one category."
)

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _build_prompt(descriptions: list[str]) -> str:
    categories = ", ".join(sorted(_VALID))
    lines = "\n".join(f"{i + 1}. {d}" for i, d in enumerate(descriptions))
    return (
        f"Categories: {categories}.\n\n"
        "Classify each numbered line below. Respond with ONLY a JSON array of "
        'lowercase category strings, exactly one per line, in order. Use "other" '
        f"if unsure.\n\n{lines}"
    )


def _extract_json_array(text: str) -> list:
    cleaned = _CODE_FENCE.sub("", text).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def llm_categorize(descriptions: list[str], provider: LLMProvider) -> list[Category]:
    """Classify ``descriptions`` via the LLM, falling back to rules on any failure."""
    if not descriptions:
        return []
    try:
        raw = provider.chat(
            [
                ChatMessage(role="system", content=_SYSTEM),
                ChatMessage(role="user", content=_build_prompt(descriptions)),
            ]
        )
        parsed = _extract_json_array(raw)
    except Exception:
        return [categorize_by_rules(d) for d in descriptions]

    result: list[Category] = []
    for i, description in enumerate(descriptions):
        value = parsed[i] if i < len(parsed) else None
        if isinstance(value, str) and value.lower() in _VALID:
            result.append(Category(value.lower()))
        else:
            result.append(categorize_by_rules(description))
    return result
