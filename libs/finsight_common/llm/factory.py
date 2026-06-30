"""Provider factory: pick a provider based on configuration."""

from __future__ import annotations

from finsight_common.config import Settings, get_settings

from .base import LLMProvider, NullProvider


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Return the best available provider for the current settings.

    Falls back to :class:`NullProvider` when nothing is configured, so importing
    and wiring this never fails at startup — only at call time.
    """
    settings = settings or get_settings()
    if settings.azure_openai_configured:
        from .azure_openai import AzureOpenAIProvider

        return AzureOpenAIProvider(settings)
    return NullProvider()
