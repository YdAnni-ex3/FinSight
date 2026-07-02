import io
import json

from finsight_common.config import Settings
from finsight_common.llm import get_provider
from finsight_common.llm.base import ChatMessage, NullProvider
from finsight_common.llm.bedrock import BedrockProvider

_MODEL = "anthropic.claude-3-5-haiku-20241022-v1:0"


class FakeBedrockClient:
    def __init__(self):
        self.calls: list = []

    def converse(self, **kwargs):
        self.calls.append(("converse", kwargs))
        return {"output": {"message": {"content": [{"text": "hello from bedrock"}]}}}

    def invoke_model(self, modelId, body):
        self.calls.append(("invoke_model", modelId, body))
        return {"body": io.BytesIO(json.dumps({"embedding": [0.1, 0.2, 0.3]}).encode())}


def _cfg(**kw):
    return Settings(bedrock_chat_model=_MODEL, **kw)


def test_chat_splits_system_and_returns_text():
    client = FakeBedrockClient()
    out = BedrockProvider(_cfg(), client=client).chat(
        [
            ChatMessage(role="system", content="be terse"),
            ChatMessage(role="user", content="hi"),
        ]
    )
    assert out == "hello from bedrock"
    _, kwargs = client.calls[0]
    assert kwargs["system"] == [{"text": "be terse"}]
    assert kwargs["messages"] == [{"role": "user", "content": [{"text": "hi"}]}]
    assert kwargs["modelId"] == _MODEL


def test_embed_returns_vectors():
    vecs = BedrockProvider(_cfg(), client=FakeBedrockClient()).embed(["a", "b"])
    assert vecs == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]


def test_factory_selects_bedrock_when_forced():
    provider = get_provider(_cfg(llm_provider="bedrock"))
    assert isinstance(provider, BedrockProvider)


def test_factory_auto_uses_bedrock_when_only_bedrock_configured():
    assert isinstance(get_provider(_cfg()), BedrockProvider)


def test_factory_null_when_nothing_configured():
    assert isinstance(get_provider(Settings()), NullProvider)
