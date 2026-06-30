"""Azure Key Vault secret access.

In the cloud, prefer this over committed env files. Falls back to the
environment when no Key Vault URL is configured, so the same code path works
locally and in production. The ``azure-*`` packages are imported lazily so the
core library has no hard dependency on them.
"""

from __future__ import annotations

import os
from functools import lru_cache

from .config import get_settings


@lru_cache
def _client():  # pragma: no cover - requires Azure SDK + credentials
    settings = get_settings()
    if not settings.key_vault_url:
        return None
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    return SecretClient(vault_url=settings.key_vault_url, credential=DefaultAzureCredential())


def get_secret(name: str, default: str | None = None) -> str | None:
    """Return a secret from Key Vault, falling back to the environment.

    ``name`` uses Key Vault naming (e.g. ``pinecone-api-key``); the env
    fallback checks the upper-cased, underscore form (``PINECONE_API_KEY``).
    """
    client = _client()
    if client is not None:
        try:
            return client.get_secret(name).value
        except Exception:  # pragma: no cover - network/permission issues
            pass
    return os.getenv(name.upper().replace("-", "_"), default)
