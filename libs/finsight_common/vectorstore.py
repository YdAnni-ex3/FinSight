"""Vector store abstraction.

Pinecone (serverless) when an API key is configured; otherwise a simple
in-memory cosine store so RAG works locally and in tests with no cloud.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .config import Settings, get_settings


@dataclass
class VectorRecord:
    id: str
    values: list[float]
    metadata: dict


@dataclass
class QueryMatch:
    id: str
    score: float
    metadata: dict


@runtime_checkable
class VectorStore(Protocol):
    def upsert(self, records: list[VectorRecord]) -> None: ...
    def query(self, vector: list[float], top_k: int = 5) -> list[QueryMatch]: ...


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class InMemoryVectorStore:
    _records: dict[str, VectorRecord] = field(default_factory=dict)

    def upsert(self, records: list[VectorRecord]) -> None:
        for record in records:
            self._records[record.id] = record

    def query(self, vector: list[float], top_k: int = 5) -> list[QueryMatch]:
        matches = [
            QueryMatch(r.id, _cosine(vector, r.values), r.metadata) for r in self._records.values()
        ]
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_k]

    def __len__(self) -> int:
        return len(self._records)


class PineconeVectorStore:
    """Serverless Pinecone index, created on first use if missing."""

    def __init__(self, settings: Settings, dim: int) -> None:
        from pinecone import Pinecone, ServerlessSpec

        client = Pinecone(api_key=settings.pinecone_api_key)
        index_list = client.list_indexes()
        existing = (
            set(index_list.names())
            if hasattr(index_list, "names")
            else {idx["name"] for idx in index_list}
        )
        if settings.pinecone_index not in existing:
            client.create_index(
                name=settings.pinecone_index,
                dimension=dim,
                metric="cosine",
                spec=ServerlessSpec(cloud=settings.pinecone_cloud, region=settings.pinecone_region),
            )
        self._index = client.Index(settings.pinecone_index)

    def upsert(self, records: list[VectorRecord]) -> None:
        self._index.upsert(
            vectors=[{"id": r.id, "values": r.values, "metadata": r.metadata} for r in records]
        )

    def query(self, vector: list[float], top_k: int = 5) -> list[QueryMatch]:
        result = self._index.query(vector=vector, top_k=top_k, include_metadata=True)
        return [QueryMatch(m["id"], m["score"], m.get("metadata", {})) for m in result["matches"]]


def get_vector_store(settings: Settings | None = None, dim: int = 1536) -> VectorStore:
    """Return Pinecone when an API key is set, else an in-memory store."""
    settings = settings or get_settings()
    if settings.pinecone_api_key:
        return PineconeVectorStore(settings, dim)
    return InMemoryVectorStore()
