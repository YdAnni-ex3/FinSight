"""Embedding providers.

Azure OpenAI embeddings when configured; otherwise a deterministic,
dependency-free hashing embedder so RAG works locally and in tests with zero
cloud calls. Both expose the same ``.dim`` and ``.embed()`` surface.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, runtime_checkable

from .config import Settings, get_settings

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    """Deterministic bag-of-words hashing embedder for offline use.

    Similar text maps to similar vectors (hashed term frequencies, L2
    normalized) — good enough for local RAG and tests without any model.
    """

    name = "hash"

    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokenize(text):
            digest = hashlib.md5(token.encode(), usedforsecurity=False).hexdigest()
            vec[int(digest, 16) % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class AzureEmbeddingProvider:
    """Azure OpenAI embeddings, via the shared LLM provider."""

    name = "azure_openai"

    def __init__(self, settings: Settings, dim: int) -> None:
        from .llm.azure_openai import AzureOpenAIProvider

        self._provider = AzureOpenAIProvider(settings)
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._provider.embed(texts)


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Return the best available embedding provider for the current settings."""
    settings = settings or get_settings()
    if settings.azure_embeddings_configured:
        return AzureEmbeddingProvider(settings, settings.embedding_dim)
    return HashEmbeddingProvider(settings.embedding_dim)
