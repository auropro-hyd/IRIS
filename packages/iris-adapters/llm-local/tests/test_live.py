"""Live tests for iris-adapter-llm-local.

Requires a running local inference server (vLLM or Ollama) and:
    IRIS_LLM_LIVE_LOCAL=1
    IRIS_LLM_LOCAL_MODEL=<model-name>
    IRIS_LLM_LOCAL_URL=<base-url>   (optional, default http://localhost:8080/v1)

Run:
    IRIS_LLM_LIVE_LOCAL=1 IRIS_LLM_LOCAL_MODEL=mistral:7b uv run pytest \
        packages/iris-adapters/llm-local/tests/test_live.py -v
"""

from __future__ import annotations

import asyncio
import os

import pytest
from iris_adapter_llm_local import LocalProvider
from iris_engine.contracts.llm_provider import LLMRequest, TenantContext

pytestmark = pytest.mark.skipif(
    os.environ.get("IRIS_LLM_LIVE_LOCAL") != "1",
    reason="Set IRIS_LLM_LIVE_LOCAL=1 to run live local LLM tests",
)

_CTX = TenantContext(tenant_id="live-test", product_slug="test/in")


def _run(coro):  # type: ignore[no-untyped-def]
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _provider() -> LocalProvider:
    return LocalProvider.from_env()


def test_live_text_round_trip() -> None:
    req = LLMRequest(prompt="Reply with the single word OK")
    result = _run(_provider().complete(_CTX, req))
    assert result.text
    assert result.adapter_id == "local"


def test_live_token_counts_nonzero() -> None:
    req = LLMRequest(prompt="Say hello")
    result = _run(_provider().complete(_CTX, req))
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0
    assert result.usage.total_tokens == result.usage.input_tokens + result.usage.output_tokens
