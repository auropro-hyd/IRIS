"""Live tests for iris-adapter-llm-openai.

Requires:
    IRIS_LLM_LIVE_OPENAI=1
    IRIS_LLM_OPENAI_API_KEY

Run:
    IRIS_LLM_LIVE_OPENAI=1 uv run pytest \
        packages/iris-adapters/llm-openai/tests/test_live.py -v
"""

from __future__ import annotations

import asyncio
import os

import pytest
from iris_adapter_llm_openai import OpenAIProvider
from iris_engine.contracts.llm_provider import LLMRequest, TenantContext

pytestmark = pytest.mark.skipif(
    os.environ.get("IRIS_LLM_LIVE_OPENAI") != "1",
    reason="Set IRIS_LLM_LIVE_OPENAI=1 to run live OpenAI tests",
)

_CTX = TenantContext(tenant_id="live-test", product_slug="test/in")


def _run(coro):  # type: ignore[no-untyped-def]
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _provider() -> OpenAIProvider:
    return OpenAIProvider.from_env()


def test_live_text_round_trip() -> None:
    req = LLMRequest(prompt="Reply with the single word OK")
    result = _run(_provider()._do_complete(_CTX, req))
    assert "ok" in result.text.lower()
    assert result.adapter_id == "openai"


def test_live_token_counts_nonzero() -> None:
    req = LLMRequest(prompt="Say hello")
    result = _run(_provider()._do_complete(_CTX, req))
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0
    assert result.usage.total_tokens == result.usage.input_tokens + result.usage.output_tokens


def test_live_auth_failure_raises() -> None:
    from iris_engine.contracts.llm_provider import LLMAuthenticationFailed

    bad = OpenAIProvider(api_key="sk-invalid")  # pragma: allowlist secret
    with pytest.raises(LLMAuthenticationFailed):
        _run(bad._do_complete(_CTX, LLMRequest(prompt="hello")))
