"""Smoke-test the live cloud wiring.

Confirms .env is correct end-to-end: Azure OpenAI chat + embeddings and
Pinecone connectivity. Run after provisioning:

    python -m uv run python scripts/verify_cloud.py
"""

from __future__ import annotations

from finsight_common.config import get_settings
from finsight_common.embeddings import get_embedding_provider
from finsight_common.llm import get_provider
from finsight_common.llm.base import ChatMessage


def main() -> None:
    settings = get_settings()
    print(f"azure chat configured:       {settings.azure_openai_configured}")
    print(f"azure embeddings configured: {settings.azure_embeddings_configured}")
    print(f"pinecone configured:         {bool(settings.pinecone_api_key)}")

    provider = get_provider(settings)
    print(f"\nchat provider: {provider.name}")
    reply = provider.chat([ChatMessage(role="user", content="Reply with exactly one word: pong")])
    print(f"chat reply: {reply!r}")

    embedder = get_embedding_provider(settings)
    vectors = embedder.embed(["swiggy order", "salary credit"])
    print(f"\nembedder: {embedder.name}, dim: {len(vectors[0])}, count: {len(vectors)}")

    if settings.pinecone_api_key:
        from pinecone import Pinecone

        client = Pinecone(api_key=settings.pinecone_api_key)
        index_list = client.list_indexes()
        names = (
            index_list.names() if hasattr(index_list, "names") else [i["name"] for i in index_list]
        )
        print(f"\npinecone indexes: {list(names)}")

    print("\nOK: cloud wiring verified.")


if __name__ == "__main__":
    main()
