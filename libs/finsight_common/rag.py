"""Retrieval-augmented Q&A over indexed transactions.

Embeds transactions into the vector store, then answers natural-language
questions by retrieving the most relevant ones and (when a chat model is
available) summarizing them. Falls back to an extractive answer with no LLM.
"""

from __future__ import annotations

from .embeddings import EmbeddingProvider
from .llm.base import ChatMessage, LLMProvider
from .models import Statement
from .vectorstore import VectorRecord, VectorStore

_SYSTEM = (
    "You answer questions about the user's personal finances using ONLY the "
    "transactions provided as context. Be concise and specific. If the context "
    "is insufficient, say so."
)


def _txn_text(date: str, description: str, amount: float, category: str) -> str:
    return f"{date} | {description} | {amount} | {category}"


class RagService:
    def __init__(
        self,
        embedder: EmbeddingProvider,
        store: VectorStore,
        chat: LLMProvider | None = None,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._chat = chat

    def index_statement(self, statement: Statement, *, source_id: str = "stmt") -> int:
        """Embed and upsert each transaction; returns the number indexed."""
        transactions = statement.transactions
        if not transactions:
            return 0
        texts = [
            _txn_text(
                t.txn_date.isoformat(),
                t.description,
                float(t.amount),
                t.category.value if t.category else "other",
            )
            for t in transactions
        ]
        vectors = self._embedder.embed(texts)
        records = [
            VectorRecord(
                id=f"{source_id}-{i}",
                values=vector,
                metadata={
                    "date": t.txn_date.isoformat(),
                    "description": t.description,
                    "amount": float(t.amount),
                    "category": t.category.value if t.category else "other",
                },
            )
            for i, (t, vector) in enumerate(zip(transactions, vectors, strict=False))
        ]
        self._store.upsert(records)
        return len(records)

    def query(self, question: str, top_k: int = 5) -> dict:
        """Retrieve the most relevant transactions and answer the question."""
        vector = self._embedder.embed([question])[0]
        matches = self._store.query(vector, top_k=top_k)
        context = [m.metadata for m in matches]
        return {"answer": self._synthesize(question, context), "matches": context}

    def _synthesize(self, question: str, context: list[dict]) -> str:
        if not context:
            return "No matching transactions found. Try indexing a statement first."
        if self._chat is not None:
            try:
                lines = "\n".join(
                    f"- {c['date']} {c['description']} {c['amount']} [{c['category']}]"
                    for c in context
                )
                return self._chat.chat(
                    [
                        ChatMessage(role="system", content=_SYSTEM),
                        ChatMessage(
                            role="user",
                            content=f"Transactions:\n{lines}\n\nQuestion: {question}",
                        ),
                    ]
                )
            except Exception:
                pass
        top = context[:3]
        return "Top matches: " + "; ".join(
            f"{c['date']} {c['description']} ({c['amount']})" for c in top
        )
