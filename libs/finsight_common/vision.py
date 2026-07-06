"""Finance slip extraction via vision LLM.

Accepts an image (JPEG, PNG, WEBP, GIF, BMP) and uses a vision-capable LLM
to extract structured transactions. Falls back to a deterministic stub when no
provider is configured so local dev never requires cloud credentials.

Architecture mirrors the LLM factory: get_slip_extractor(settings) returns the
best available extractor without the caller knowing which backend is used.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .categorize import categorize_by_rules
from .config import Settings
from .models import Category, Transaction

log = logging.getLogger(__name__)

_TODAY_PLACEHOLDER = "{today}"

_EXTRACTION_PROMPT = (
    "You are a financial data extractor. Given the image of a finance document "
    "(restaurant bill, utility receipt, handwritten expense note, UPI screenshot, "
    "bank statement page, grocery receipt, etc.), extract every transaction or "
    "line item that is visible.\n\n"
    "Return ONLY valid JSON — no markdown fences, no explanation:\n"
    '{"transactions": [{"date": "YYYY-MM-DD", "description": "item or merchant", "amount": -123.45}]}\n\n'
    "Rules:\n"
    "- amount is NEGATIVE for expenses/debits and POSITIVE for income/credits\n"
    "- If a date is not clearly visible, use today's date: " + _TODAY_PLACEHOLDER + "\n"
    "- Use INR amounts by default; if another currency is shown note it in the description\n"
    "- If a total AND line items are both visible, prefer line items\n"
    "- Trim descriptions to ≤80 characters\n"
    "- Append '(uncertain)' to any description you cannot read clearly\n"
    "- Omit zero-amount rows (tax breakdowns that sum to 0, headers, etc.)"
)


class SlipExtractor:
    """Base class — subclasses implement :meth:`extract`."""

    def extract(self, image_bytes: bytes, mime_type: str) -> list[Transaction]:
        raise NotImplementedError


class StubExtractor(SlipExtractor):
    """Returns a small fixed result used in local dev / tests.

    Configured automatically when no vision-capable cloud provider is available.
    """

    name = "stub"

    def extract(self, image_bytes: bytes, mime_type: str) -> list[Transaction]:
        today = date.today()
        return [
            Transaction(
                txn_date=today,
                description="Restaurant bill (stub — configure vision LLM for real extraction)",
                amount=Decimal("-450.00"),
                category=Category.DINING,
            ),
            Transaction(
                txn_date=today,
                description="GST 18% (stub)",
                amount=Decimal("-81.00"),
                category=Category.OTHER,
            ),
        ]


class AzureVisionExtractor(SlipExtractor):
    """Uses Azure OpenAI vision (gpt-4o / gpt-5) to extract transactions."""

    name = "azure_openai_vision"

    def __init__(self, settings: Settings) -> None:
        from openai import AzureOpenAI

        self._settings = settings
        self._client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )

    def extract(self, image_bytes: bytes, mime_type: str) -> list[Transaction]:
        b64 = base64.b64encode(image_bytes).decode()
        data_url = f"data:{mime_type};base64,{b64}"
        prompt = _EXTRACTION_PROMPT.replace(_TODAY_PLACEHOLDER, date.today().isoformat())
        try:
            response = self._client.chat.completions.create(
                model=self._settings.azure_openai_chat_deployment,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                        ],
                    }
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            raw = response.choices[0].message.content or "{}"
        except Exception as exc:
            # Older deployments may not support vision — fall back gracefully.
            log.warning("Azure vision call failed (%s), returning empty extraction", exc)
            return []
        return _parse_extraction(raw)


class BedrockVisionExtractor(SlipExtractor):
    """Uses AWS Bedrock (Claude 3.x / Nova Pro/Lite) for vision extraction."""

    name = "bedrock_vision"

    def __init__(self, settings: Settings) -> None:
        import boto3

        self._settings = settings
        self._client = boto3.client("bedrock-runtime", region_name=settings.aws_region)

    def extract(self, image_bytes: bytes, mime_type: str) -> list[Transaction]:
        prompt = _EXTRACTION_PROMPT.replace(_TODAY_PLACEHOLDER, date.today().isoformat())
        fmt = mime_type.split("/")[-1].lower()
        # Bedrock accepts: jpeg, png, gif, webp
        if fmt in ("jpg",):
            fmt = "jpeg"
        if fmt not in {"jpeg", "png", "gif", "webp"}:
            fmt = "jpeg"
        try:
            response = self._client.converse(
                modelId=self._settings.bedrock_chat_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"text": prompt},
                            {"image": {"format": fmt, "source": {"bytes": image_bytes}}},
                        ],
                    }
                ],
                inferenceConfig={"temperature": 0.0, "maxTokens": 1024},
            )
            raw = response["output"]["message"]["content"][0]["text"]
        except Exception as exc:
            log.warning("Bedrock vision call failed (%s), returning empty extraction", exc)
            return []
        return _parse_extraction(raw)


# ── helpers ────────────────────────────────────────────────────────────────────


def _parse_extraction(raw: str) -> list[Transaction]:
    """Parse the LLM's JSON response into :class:`Transaction` objects."""
    text = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Vision LLM returned non-JSON: %.200s", text)
        return []

    transactions: list[Transaction] = []
    today = date.today()
    for item in data.get("transactions", []):
        raw_date = item.get("date") or today.isoformat()
        try:
            txn_date = date.fromisoformat(str(raw_date)[:10])
        except ValueError:
            txn_date = today
        description = str(item.get("description", "unknown"))[:120].strip()
        try:
            amount = Decimal(str(item.get("amount", 0)))
        except InvalidOperation:
            continue
        if amount == 0:
            continue
        category = categorize_by_rules(description)
        transactions.append(
            Transaction(
                txn_date=txn_date,
                description=description,
                amount=amount,
                category=category,
            )
        )
    return transactions


def get_slip_extractor(settings: Settings) -> SlipExtractor:
    """Factory: return the best available vision extractor given current settings.

    Priority: Azure OpenAI (vision capable) → Bedrock → stub.
    """
    if settings.azure_openai_configured:
        return AzureVisionExtractor(settings)
    if settings.bedrock_configured:
        return BedrockVisionExtractor(settings)
    log.info("No vision LLM configured — using stub extractor")
    return StubExtractor()
