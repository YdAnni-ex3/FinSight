"""Azure OpenAI provider.

Wraps the official ``openai`` SDK's ``AzureOpenAI`` client. Imported lazily by
the factory so the dependency is only required when this provider is used.
"""

from __future__ import annotations

from finsight_common.config import Settings

from .base import ChatMessage


class AzureOpenAIProvider:
    name = "azure_openai"

    def __init__(self, settings: Settings) -> None:
        from openai import AzureOpenAI

        self._settings = settings
        self._client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )

    def chat(self, messages: list[ChatMessage], *, temperature: float = 0.0) -> str:
        response = self._client.chat.completions.create(
            model=self._settings.azure_openai_chat_deployment,
            messages=[m.model_dump() for m in messages],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(
            model=self._settings.azure_openai_embeddings_deployment,
            input=texts,
        )
        return [item.embedding for item in response.data]
