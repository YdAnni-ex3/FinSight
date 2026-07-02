"""Provider factory: pick a provider based on configuration."""

from __future__ import annotations

from finsight_common.config import Settings, get_settings

from .base import LLMProvider, NullProvider


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Return the best available provider for the current settings.

    Honors ``llm_provider`` ("auto" | "azure" | "bedrock"); "auto" prefers Azure
    OpenAI, then Bedrock. Falls back to :class:`NullProvider` when nothing is
    configured, so wiring never fails at startup — only at call time.
    """
    settings = settings or get_settings()
    choice = (settings.llm_provider or "auto").lower()

    if choice == "bedrock" and settings.bedrock_configured:
        return _bedrock(settings)
    if choice == "azure" and settings.azure_openai_configured:
        return _azure(settings)

    if settings.azure_openai_configured:
        return _azure(settings)
    if settings.bedrock_configured:
        return _bedrock(settings)
    return NullProvider()


def _azure(settings: Settings) -> LLMProvider:
    from .azure_openai import AzureOpenAIProvider

    return AzureOpenAIProvider(settings)


def _bedrock(settings: Settings) -> LLMProvider:
    from .bedrock import BedrockProvider

    return BedrockProvider(settings)
