"""AWS Bedrock provider.

Implements the same :class:`LLMProvider` surface as Azure OpenAI using Bedrock's
unified ``converse`` API for chat and Titan embeddings. boto3 is imported lazily
and the client is injectable, so this is testable without AWS. Credentials come
from the standard AWS chain (env vars, ``~/.aws``, or an instance role).
"""

from __future__ import annotations

import json

from finsight_common.config import Settings

from .base import ChatMessage


class BedrockProvider:
    name = "bedrock"

    def __init__(self, settings: Settings, client=None) -> None:
        self._settings = settings
        self._client = client  # created lazily on first use if not injected

    def _get_client(self):
        if self._client is None:  # pragma: no cover - needs boto3 + AWS creds
            import boto3

            self._client = boto3.client("bedrock-runtime", region_name=self._settings.aws_region)
        return self._client

    def chat(self, messages: list[ChatMessage], *, temperature: float = 0.0) -> str:
        system = [{"text": m.content} for m in messages if m.role == "system"]
        conversation = [
            {
                "role": "assistant" if m.role == "assistant" else "user",
                "content": [{"text": m.content}],
            }
            for m in messages
            if m.role != "system"
        ]
        kwargs = {
            "modelId": self._settings.bedrock_chat_model,
            "messages": conversation,
            "inferenceConfig": {"temperature": temperature},
        }
        if system:
            kwargs["system"] = system
        response = self._get_client().converse(**kwargs)
        return response["output"]["message"]["content"][0]["text"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        vectors: list[list[float]] = []
        for text in texts:
            response = client.invoke_model(
                modelId=self._settings.bedrock_embed_model,
                body=json.dumps({"inputText": text}),
            )
            payload = json.loads(response["body"].read())
            vectors.append(payload["embedding"])
        return vectors
