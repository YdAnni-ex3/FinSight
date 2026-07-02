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

    if settings.snowflake_configured:
        from datetime import date
        from decimal import Decimal

        from finsight_common.models import Category, Transaction
        from finsight_common.warehouse import get_transaction_store

        store = get_transaction_store(settings)
        before = len(store.all())
        store.add(
            [
                Transaction(
                    txn_date=date(2024, 1, 1),
                    description="verify ping",
                    amount=Decimal("-1"),
                    category=Category.OTHER,
                )
            ],
            source_id="__verify__",
        )
        after = len(store.all())
        print(
            f"\nsnowflake store ({store.__class__.__name__}): "
            f"{before} -> {after} rows (round-trip OK)"
        )

        import snowflake.connector

        conn = snowflake.connector.connect(
            account=settings.snowflake_account,
            user=settings.snowflake_user,
            password=settings.snowflake_password,
            warehouse=settings.snowflake_warehouse,
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            role=settings.snowflake_role or None,
        )
        conn.cursor().execute("DELETE FROM FACT_TRANSACTION WHERE source_file = '__verify__'")
        conn.commit()
        conn.close()
        print("snowflake store: verify row cleaned up")

    print("\nOK: cloud wiring verified.")


if __name__ == "__main__":
    main()
