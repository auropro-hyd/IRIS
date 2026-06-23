"""Live tests for iris-llm-azure-openai.

Requires:
    IRIS_LLM_LIVE_AZURE=1
    IRIS_LLM_AZURE_RESOURCE
    IRIS_LLM_AZURE_API_KEY
    IRIS_LLM_AZURE_DEPLOYMENT_CHAT
    IRIS_LLM_AZURE_DEPLOYMENT_EXTRACT
    IRIS_LLM_AZURE_API_VERSION  (optional, defaults to 2024-02-01)

Run:
    IRIS_LLM_LIVE_AZURE=1 uv run pytest \
        packages/iris-adapters/llm-azure-openai/tests/test_live.py -v
"""

from __future__ import annotations

import asyncio
import os

import pytest
from iris_adapter_llm_azure_openai import AzureOpenAIProvider
from iris_engine.contracts.llm_provider import LLMRequest, TenantContext

pytestmark = pytest.mark.skipif(
    os.environ.get("IRIS_LLM_LIVE_AZURE") != "1",
    reason="Set IRIS_LLM_LIVE_AZURE=1 to run live Azure OpenAI tests",
)

_CTX = TenantContext(tenant_id="live-test", product_slug="test/in")


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.new_event_loop().run_until_complete(coro)


def _provider() -> AzureOpenAIProvider:
    return AzureOpenAIProvider.from_env()


def test_live_text_round_trip() -> None:
    req = LLMRequest(prompt="Reply with the single word OK")
    result = _run(_provider()._do_complete(_CTX, req))
    assert "ok" in result.text.lower()
    assert result.adapter_id == "azure-openai"


def test_live_token_counts_nonzero() -> None:
    req = LLMRequest(prompt="Say hello")
    result = _run(_provider()._do_complete(_CTX, req))
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0
    assert result.usage.total_tokens == result.usage.input_tokens + result.usage.output_tokens


def test_live_auth_failure_raises() -> None:
    from iris_engine.contracts.llm_provider import LLMAuthenticationFailed

    bad = AzureOpenAIProvider(
        resource=os.environ.get("IRIS_LLM_AZURE_RESOURCE", "bad"),
        api_key="sk-invalid",  # pragma: allowlist secret
        deployment_chat=os.environ.get("IRIS_LLM_AZURE_DEPLOYMENT_CHAT", "bad"),
        deployment_extract=os.environ.get("IRIS_LLM_AZURE_DEPLOYMENT_EXTRACT", "bad"),
    )
    with pytest.raises(LLMAuthenticationFailed):
        _run(bad._do_complete(_CTX, LLMRequest(prompt="hello")))
