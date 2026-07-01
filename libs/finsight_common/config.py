"""Application settings.

Values come from environment variables (prefixed ``FINSIGHT_``) or a local
``.env`` file. In the cloud, secrets should be sourced from Azure Key Vault
(see :mod:`finsight_common.keyvault`) rather than committed env files.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FINSIGHT_",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "local"
    log_level: str = "INFO"

    # CORS: comma-separated allowed origins ("*" = allow all, dev only).
    cors_origins: str = "*"
    cors_origin_regex: str | None = None

    # Postgres (serving / OLTP store)
    database_url: str = "postgresql://finsight:finsight@localhost:5432/finsight"

    # Azure Blob Storage
    blob_connection_string: str | None = None
    blob_container: str = "raw-statements"

    # Azure OpenAI / Microsoft Foundry
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str | None = None
    azure_openai_embeddings_deployment: str | None = None

    # Azure Key Vault (prod secret source)
    key_vault_url: str | None = None

    # Pinecone
    pinecone_api_key: str | None = None
    pinecone_index: str = "finsight"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # Embeddings
    embedding_dim: int = 1536

    # Kafka / Redpanda
    kafka_bootstrap_servers: str = "localhost:9092"

    # Snowflake (analytics warehouse + persistent transaction store)
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_warehouse: str = "COMPUTE_WH"
    snowflake_database: str = "FINSIGHT"
    snowflake_schema: str = "ANALYTICS"
    snowflake_role: str | None = None

    @property
    def azure_openai_configured(self) -> bool:
        """True when enough is set to make a live Azure OpenAI chat call."""
        return bool(
            self.azure_openai_endpoint
            and self.azure_openai_api_key
            and self.azure_openai_chat_deployment
        )

    @property
    def azure_embeddings_configured(self) -> bool:
        """True when an Azure OpenAI embeddings deployment is available."""
        return bool(
            self.azure_openai_endpoint
            and self.azure_openai_api_key
            and self.azure_openai_embeddings_deployment
        )

    @property
    def snowflake_configured(self) -> bool:
        """True when Snowflake credentials are present."""
        return bool(self.snowflake_account and self.snowflake_user and self.snowflake_password)


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
