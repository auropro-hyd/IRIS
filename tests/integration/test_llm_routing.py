"""Integration tests for LLM adapter routing via product config (DoD items 4 and 5).

Item 4: A Product with adapters.llm: <name> routes calls through the named adapter,
        verified by the OTEL span's llm.adapter_id attribute.

Item 5: Structured output (Pydantic schema) round-trips through every adapter.
        (Also covered by C-LLM-005 in the contract suite.)

The full path under test:
    ProductSchema.adapters.llm  ->  select_llm_provider(registry, adapter_id)
    ->  provider.complete()  ->  OTEL span  ->  result

All providers use injected mock httpx clients; no real network calls.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from iris_adapter_llm_anthropic import AnthropicProvider
from iris_adapter_llm_azure_openai import AzureOpenAIProvider
from iris_adapter_llm_local import LocalProvider
from iris_adapter_llm_openai import OpenAIProvider
from iris_adapter_llm_shared.retry import RetryConfig
from iris_config.schema.adapters import AdaptersSchema
from iris_engine.contracts.llm_provider import (
    LLMRateLimited,
    LLMRequest,
    TenantContext,
)
from iris_engine.llm.selector import select_llm_provider
from pydantic import BaseModel

pytestmark = pytest.mark.integration

_CTX = TenantContext(tenant_id="routing-test", product_slug="test/in")
_REQ = LLMRequest(prompt="Reply with the single word OK")
_NO_RETRY = RetryConfig(max_retries=0, backoff_ms=0)


# ── response helpers ──────────────────────────────────────────────────────────


def _openai_resp(text: str = "OK") -> httpx.Response:
    body = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    return httpx.Response(200, json=body)


def _anthropic_resp(text: str = "OK") -> httpx.Response:
    body = {
        "model": "claude-haiku-4-5-20251001",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    return httpx.Response(200, json=body)


def _mock_client(response: httpx.Response) -> MagicMock:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=response)
    return client


# ── registry factory ──────────────────────────────────────────────────────────


def _build_registry(openai_resp: httpx.Response | None = None) -> dict[str, Any]:
    """Build a registry of all four adapters with mocked HTTP clients."""
    return {
        "openai": OpenAIProvider(
            api_key="sk-test",  # pragma: allowlist secret
            _http_client=_mock_client(openai_resp or _openai_resp()),
            retry_config=_NO_RETRY,
        ),
        "azure-openai": AzureOpenAIProvider(
            resource="test",
            api_key="az-key",  # pragma: allowlist secret
            deployment_chat="chat",
            deployment_extract="extract",
            _http_client=_mock_client(openai_resp or _openai_resp()),
            retry_config=_NO_RETRY,
        ),
        "anthropic": AnthropicProvider(
            api_key="sk-ant-test",  # pragma: allowlist secret
            _http_client=_mock_client(_anthropic_resp()),
            retry_config=_NO_RETRY,
        ),
        "local": LocalProvider(
            model="mistral:7b",
            _http_client=_mock_client(openai_resp or _openai_resp()),
            retry_config=_NO_RETRY,
        ),
    }


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── DoD item 4: routing verified by adapter telemetry ────────────────────────


@pytest.mark.parametrize(
    "llm_adapter,expected_id",
    [
        ("anthropic", "anthropic"),
        ("openai", "openai"),
        ("azure-openai", "azure-openai"),
        ("local", "local"),
    ],
)
def test_product_config_routes_to_correct_adapter(
    llm_adapter: str,
    expected_id: str,
    span_exporter: Any,
) -> None:
    """Product config adapters.llm routes to the named adapter; span confirms it."""
    adapters = AdaptersSchema(ocr="local", llm=llm_adapter)  # type: ignore[arg-type]

    registry = _build_registry()
    provider = select_llm_provider(registry, adapters.llm)

    result = _run(provider.complete(_CTX, _REQ))

    assert result.adapter_id == expected_id

    spans = span_exporter.get_finished_spans()
    assert spans, "no spans emitted"
    assert spans[-1].attributes.get("llm.adapter_id") == expected_id
    assert spans[-1].attributes.get("llm.tenant_id") == _CTX.tenant_id


# ── DoD item 5: structured output round-trips through every adapter ───────────


class _Invoice(BaseModel):
    vendor: str
    total: float


@pytest.mark.parametrize("llm_adapter", ["openai", "azure-openai", "local"])
def test_structured_output_round_trip_openai_compat(llm_adapter: str) -> None:
    """Pydantic schema round-trips through OpenAI-compatible adapters."""
    payload = json.dumps({"vendor": "Acme Corp", "total": 99.95})
    registry = _build_registry(openai_resp=_openai_resp(text=payload))
    provider = select_llm_provider(registry, llm_adapter)
    req = LLMRequest(prompt="extract invoice", schema=_Invoice)
    result = _run(provider._do_complete(_CTX, req))
    assert isinstance(result.structured, _Invoice)
    assert result.structured.vendor == "Acme Corp"
    assert result.structured.total == pytest.approx(99.95)


# ── Fallback behaviour ────────────────────────────────────────────────────────


def _failing_client(exc: Exception) -> MagicMock:
    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=exc)
    return client


def test_fallback_fires_on_unavailable() -> None:
    """LLMUnavailable on the primary triggers the fallback provider."""
    primary = OpenAIProvider(
        api_key="sk-test",  # pragma: allowlist secret
        _http_client=_failing_client(httpx.ConnectError("down")),
        retry_config=_NO_RETRY,
    )
    fallback = OpenAIProvider(
        api_key="sk-test",  # pragma: allowlist secret
        _http_client=_mock_client(_openai_resp()),
        retry_config=_NO_RETRY,
    )
    registry = {"openai": primary, "openai-fallback": fallback}
    provider = select_llm_provider(registry, "openai", fallback_id="openai-fallback")
    result = _run(provider.complete(_CTX, _REQ))
    assert "OK" in result.text


def test_fallback_does_not_fire_on_rate_limited() -> None:
    """LLMRateLimited surfaces to the caller; fallback must not absorb it."""
    primary = OpenAIProvider(
        api_key="sk-test",  # pragma: allowlist secret
        _http_client=_mock_client(httpx.Response(429)),
        retry_config=_NO_RETRY,
    )
    fallback = OpenAIProvider(
        api_key="sk-test",  # pragma: allowlist secret
        _http_client=_mock_client(_openai_resp()),
        retry_config=_NO_RETRY,
    )
    registry = {"openai": primary, "openai-fallback": fallback}
    provider = select_llm_provider(registry, "openai", fallback_id="openai-fallback")
    with pytest.raises(LLMRateLimited):
        _run(provider.complete(_CTX, _REQ))


def test_structured_output_round_trip_anthropic() -> None:
    """Pydantic schema round-trips through the Anthropic tool-use adapter."""
    tool_body = {
        "model": "claude-haiku-4-5-20251001",
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "tool_use",
                "name": "structured_output",
                "input": {"vendor": "Acme Corp", "total": 99.95},
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    provider = AnthropicProvider(
        api_key="sk-ant-test",  # pragma: allowlist secret
        _http_client=_mock_client(httpx.Response(200, json=tool_body)),
        retry_config=_NO_RETRY,
    )
    req = LLMRequest(prompt="extract invoice", schema=_Invoice)
    result = _run(provider._do_complete(_CTX, req))
    assert isinstance(result.structured, _Invoice)
    assert result.structured.vendor == "Acme Corp"
    assert result.structured.total == pytest.approx(99.95)
