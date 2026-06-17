"""LLM subsystem: provider selection, in-memory stub, and OTEL instrumentation.

Key exports:
    LLMProvider: the Protocol every LLM adapter implements.
    select_llm_provider(): returns the configured provider with optional fallback.
    StubLLMProvider: in-memory fake for tests and local development.
"""

from iris_engine.contracts.llm_provider import LLMProvider, LLMRequest, LLMResponse, LLMUsage
from iris_engine.llm.in_memory import StubLLMProvider
from iris_engine.llm.selector import select_llm_provider

__all__ = [
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LLMUsage",
    "StubLLMProvider",
    "select_llm_provider",
]
