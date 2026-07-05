"""Smoke-test the AWS Bedrock provider using credentials from .env.

Loads AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from .env into the process
environment (boto3 reads the standard credential chain), then sends one chat
message through the configured BedrockProvider and prints PASS/FAIL. Run this
before flipping the live app over to Bedrock.

Usage:
    python -m uv run python scripts/verify_bedrock.py
"""

from __future__ import annotations

import os
from pathlib import Path

from finsight_common import get_settings
from finsight_common.llm import get_provider
from finsight_common.llm.base import ChatMessage


def _load_aws_creds_from_env_file() -> None:
    env_file = Path(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
            os.environ[key] = value.strip()


def main() -> None:
    _load_aws_creds_from_env_file()
    settings = get_settings()
    provider = get_provider(settings)
    print(
        f"provider={provider.name} "
        f"model={settings.bedrock_chat_model} region={settings.aws_region}"
    )
    if provider.name != "bedrock":
        print("SMOKE: SKIP - provider is not bedrock (set FINSIGHT_LLM_PROVIDER=bedrock in .env)")
        return
    try:
        reply = provider.chat([ChatMessage(role="user", content="Reply with exactly: Bedrock OK")])
        print("reply:", reply)
        print("SMOKE: PASS")
    except Exception as exc:
        print("SMOKE: FAIL", type(exc).__name__, str(exc)[:500])


if __name__ == "__main__":
    main()
