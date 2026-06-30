"""Live integration tests for iris-adapter-llm-anthropic.

Gated on IRIS_LLM_LIVE_ANTHROPIC=1 and IRIS_LLM_ANTHROPIC_API_KEY.
Run with:
  IRIS_LLM_LIVE_ANTHROPIC=1 uv run pytest packages/iris-adapters/llm-anthropic/tests/test_live.py -v
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest
from iris_adapter_llm_anthropic import AnthropicProvider
from iris_engine.contracts.llm_provider import LLMRequest, TenantContext
from pydantic import BaseModel

pytestmark = pytest.mark.skipif(
    os.environ.get("IRIS_LLM_LIVE_ANTHROPIC") != "1",
    reason="IRIS_LLM_LIVE_ANTHROPIC=1 not set",
)

_CTX = TenantContext(tenant_id="live-test", product_slug="iris/live")


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def provider() -> AnthropicProvider:
    return AnthropicProvider.from_env()


def test_live_text_response(provider: AnthropicProvider) -> None:
    req = LLMRequest(prompt='Reply with the single word "PONG" and nothing else.')
    result = _run(provider.complete(_CTX, req))
    assert "PONG" in result.text
    assert result.adapter_id == "anthropic"
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0


def test_live_structured_output(provider: AnthropicProvider) -> None:
    class _Answer(BaseModel):
        answer: str
        confidence: float

    req = LLMRequest(
        prompt="What is 2 + 2? Reply with answer as a string and confidence as a float.",
        schema=_Answer,
    )
    result = _run(provider.complete(_CTX, req))
    assert isinstance(result.structured, _Answer)
    assert "4" in result.structured.answer
    assert 0.0 <= result.structured.confidence <= 1.0


def test_live_system_prompt(provider: AnthropicProvider) -> None:
    req = LLMRequest(
        prompt="What colour should I say?",
        system="Always respond with the single word BLUE and nothing else.",
    )
    result = _run(provider.complete(_CTX, req))
    assert "BLUE" in result.text
