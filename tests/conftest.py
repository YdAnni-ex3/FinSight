"""Pytest session setup.

Force FinSight into fully-offline mode for the test suite, regardless of any
local ``.env`` that configures Azure OpenAI or Pinecone. This keeps tests
deterministic and free of network calls and cost; the real cloud paths are
verified manually, not in unit tests. Env vars take precedence over ``.env`` in
pydantic-settings, so blanking them here disables the cloud providers.
"""

import os

_OFFLINE_KEYS = (
    "FINSIGHT_AZURE_OPENAI_ENDPOINT",
    "FINSIGHT_AZURE_OPENAI_API_KEY",
    "FINSIGHT_AZURE_OPENAI_CHAT_DEPLOYMENT",
    "FINSIGHT_AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT",
    "FINSIGHT_PINECONE_API_KEY",
    "FINSIGHT_SNOWFLAKE_ACCOUNT",
    "FINSIGHT_SNOWFLAKE_USER",
    "FINSIGHT_SNOWFLAKE_PASSWORD",
    "FINSIGHT_BEDROCK_CHAT_MODEL",
)

for _key in _OFFLINE_KEYS:
    os.environ[_key] = ""
