"""LLM provider abstraction.

A single :class:`LLMProvider` interface lets the rest of the app stay
provider-agnostic. Azure OpenAI is the default; AWS Bedrock plugs in behind the
same interface during the multi-cloud phase.
"""

from .base import ChatMessage, LLMProvider, NullProvider
from .factory import get_provider

__all__ = ["ChatMessage", "LLMProvider", "NullProvider", "get_provider"]
