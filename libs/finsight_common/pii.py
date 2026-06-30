"""PII redaction.

A real PII pass must run before any statement text reaches an external LLM or
vector store (checklist Part 7.3). Uses Microsoft Presidio when installed; if
it is not available, falls back to a deterministic regex redactor tuned for
Indian financial documents (PAN, Aadhaar, IFSC, account/card numbers) plus
emails and phone numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Order matters: longer/more-specific patterns first so they win over generic
# digit runs (e.g. a 16-digit card must match before the 12-digit Aadhaar rule).
# EMAIL also covers UPI VPAs (name@bank), which have no TLD.
_REGEX_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w.-]+\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("AADHAAR", re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")),
    ("PHONE", re.compile(r"\b(?:\+?91[-\s]?)?[6-9]\d{9}\b")),
    ("ACCOUNT", re.compile(r"\b\d{9,18}\b")),
]


@dataclass
class Redactor:
    """Redacts PII from free text.

    Parameters
    ----------
    use_presidio:
        When ``True`` (default), use Presidio if it is importable. Set to
        ``False`` to force the regex fallback (used in tests for determinism).
    """

    use_presidio: bool = True

    def __post_init__(self) -> None:
        self._engine = self._build_presidio() if self.use_presidio else None

    def _build_presidio(self):
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine

            return (AnalyzerEngine(), AnonymizerEngine())
        except Exception:
            # Presidio (or its spaCy model) not installed — use regex fallback.
            return None

    def redact(self, text: str) -> str:
        if not text:
            return text
        if self._engine is not None:  # pragma: no cover - requires presidio + model
            analyzer, anonymizer = self._engine
            results = analyzer.analyze(text=text, language="en")
            return anonymizer.anonymize(text=text, analyzer_results=results).text
        return self._redact_regex(text)

    @staticmethod
    def _redact_regex(text: str) -> str:
        for label, pattern in _REGEX_PATTERNS:
            text = pattern.sub(f"<{label}>", text)
        return text


_default = Redactor()


def redact_text(text: str) -> str:
    """Redact PII from ``text`` using the default redactor."""
    return _default.redact(text)
