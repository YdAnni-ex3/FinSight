"""LLM provider interface and a no-op fallback."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal surface every provider must implement."""

    name: str

    def chat(self, messages: list[ChatMessage], *, temperature: float = 0.0) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class NullProvider:
    """Fallback used when no real provider is configured.

    Keeps local development and tests working without cloud credentials by
    failing loudly only when a call is actually made.
    """

    name = "null"

    def chat(self, messages: list[ChatMessage], *, temperature: float = 0.0) -> str:
        raise RuntimeError(
            "No LLM provider configured. Set Azure OpenAI settings (FINSIGHT_AZURE_OPENAI_*)."
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError(
            "No LLM provider configured. Set Azure OpenAI settings (FINSIGHT_AZURE_OPENAI_*)."
        )
