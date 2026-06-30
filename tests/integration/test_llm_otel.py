"""Integration tests for LLM adapter OTEL span instrumentation (T049).

Verifies that every adapter's complete() emits a span with the attributes
required by C-LLM-011. OTEL wiring lives in iris_engine.llm.tracing and is
shared by all adapters via instrument_complete().

All adapters use injected mock httpx clients - no real network calls.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from iris_adapter_llm_anthropic import AnthropicProvider
from iris_adapter_llm_azure_openai import AzureOpenAIProvider
from iris_adapter_llm_local import LocalProvider
from iris_adapter_llm_openai import OpenAIProvider
from iris_adapter_llm_shared.retry import RetryConfig
from iris_engine.contracts.llm_provider import LLMAuthenticationFailed, LLMRequest, TenantContext
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

pytestmark = pytest.mark.integration

_CTX = TenantContext(tenant_id="otel-test-tenant", product_slug="test/in")
_REQ = LLMRequest(prompt="Reply with the single word OK")

_NO_RETRY = RetryConfig(max_retries=0, backoff_ms=0)


def _openai_resp() -> httpx.Response:
    body = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    return httpx.Response(200, json=body)


def _anthropic_resp() -> httpx.Response:
    body = {
        "model": "claude-haiku-4-5-20251001",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "OK"}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    return httpx.Response(200, json=body)


def _mock_client(response: httpx.Response) -> MagicMock:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=response)
    return client


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


_REQUIRED_SPAN_ATTRS = (
    "llm.tenant_id",
    "llm.adapter_id",
    "llm.model",
    "llm.input_tokens",
    "llm.output_tokens",
    "llm.latency_ms",
    "llm.structured_output_used",
    "llm.retry_count",
)


def _assert_span(exporter: InMemorySpanExporter, expected_adapter_id: str) -> None:
    spans = exporter.get_finished_spans()
    assert spans, "no spans emitted"
    attrs = spans[-1].attributes or {}
    for key in _REQUIRED_SPAN_ATTRS:
        assert key in attrs, f"missing span attribute: {key}"
    assert attrs["llm.adapter_id"] == expected_adapter_id
    assert attrs["llm.tenant_id"] == _CTX.tenant_id


def test_openai_span_attributes(span_exporter: Any) -> None:
    provider = OpenAIProvider(
        api_key="sk-test",  # pragma: allowlist secret
        _http_client=_mock_client(_openai_resp()),
        retry_config=_NO_RETRY,
    )
    _run(provider.complete(_CTX, _REQ))
    _assert_span(span_exporter, "openai")


def test_azure_openai_span_attributes(span_exporter: Any) -> None:
    provider = AzureOpenAIProvider(
        resource="test-resource",
        api_key="az-key",  # pragma: allowlist secret
        deployment_chat="chat",
        deployment_extract="extract",
        _http_client=_mock_client(_openai_resp()),
        retry_config=_NO_RETRY,
    )
    _run(provider.complete(_CTX, _REQ))
    _assert_span(span_exporter, "azure-openai")


def test_anthropic_span_attributes(span_exporter: Any) -> None:
    provider = AnthropicProvider(
        api_key="sk-ant-test",  # pragma: allowlist secret
        _http_client=_mock_client(_anthropic_resp()),
        retry_config=_NO_RETRY,
    )
    _run(provider.complete(_CTX, _REQ))
    _assert_span(span_exporter, "anthropic")


def test_local_span_attributes(span_exporter: Any) -> None:
    provider = LocalProvider(
        model="mistral:7b",
        _http_client=_mock_client(_openai_resp()),
        retry_config=_NO_RETRY,
    )
    _run(provider.complete(_CTX, _REQ))
    _assert_span(span_exporter, "local")


def test_error_path_span_status_and_category(span_exporter: Any) -> None:
    """A typed LLM error sets StatusCode.ERROR, llm.success=False, and llm.error_category."""
    provider = OpenAIProvider(
        api_key="sk-test",  # pragma: allowlist secret
        _http_client=_mock_client(httpx.Response(401)),
        retry_config=_NO_RETRY,
    )
    with pytest.raises(LLMAuthenticationFailed):
        _run(provider.complete(_CTX, _REQ))

    spans = span_exporter.get_finished_spans()
    assert spans, "no spans emitted"
    span = spans[-1]
    assert span.status.status_code == StatusCode.ERROR
    attrs = span.attributes or {}
    assert attrs.get("llm.success") is False
    assert attrs.get("llm.error_category") == "LLMAuthenticationFailed"
