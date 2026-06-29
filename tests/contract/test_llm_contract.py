"""Parametrised LLM contract suite.

Clauses C-LLM-001 through C-LLM-011 and C-LLM-LOCAL-001 verified against
all four adapters: openai, azure-openai, anthropic, local.

All adapters use injected mock httpx.AsyncClient instances - no real network
calls are made.

C-LLM-009 tests the output-truncation signal (finish_reason=length /
stop_reason=max_tokens). Pre-flight input-size rejection surfaces as
LLMInvalidRequest; see PR #45 for the rationale.
"""

from __future__ import annotations

import asyncio
import json
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from iris_adapter_llm_anthropic import AnthropicProvider
from iris_adapter_llm_azure_openai import AzureOpenAIProvider
from iris_adapter_llm_local import LocalProvider
from iris_adapter_llm_openai import OpenAIProvider
from iris_adapter_llm_shared.retry import RetryConfig
from iris_engine.contracts.llm_provider import (
    LLMAuthenticationFailed,
    LLMContextWindowExceeded,
    LLMRateLimited,
    LLMRequest,
    LLMSchemaViolation,
    TenantContext,
)
from pydantic import BaseModel

pytestmark = pytest.mark.contract

_CTX = TenantContext(tenant_id="contract-tenant", product_slug="test/in")
_REQ = LLMRequest(prompt="Reply with the single word OK")

_ALL = ["openai", "azure_openai", "anthropic", "local"]
_VALID_IDS = {"openai", "azure-openai", "anthropic", "local"}


# ── response factories ────────────────────────────────────────────────────────


def _openai_resp(
    text: str = "OK",
    finish_reason: str = "stop",
    input_tokens: int = 10,
    output_tokens: int = 5,
    status: int = 200,
) -> httpx.Response:
    body = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": text}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
    }
    return httpx.Response(status, json=body)


def _anthropic_resp(
    text: str = "OK",
    stop_reason: str = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 5,
    status: int = 200,
) -> httpx.Response:
    body = {
        "model": "claude-haiku-4-5-20251001",
        "stop_reason": stop_reason,
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
    return httpx.Response(status, json=body)


def _default_resp(adapter_id: str, **kw: Any) -> httpx.Response:
    return _anthropic_resp(**kw) if adapter_id == "anthropic" else _openai_resp(**kw)


def _truncation_resp(adapter_id: str) -> httpx.Response:
    return (
        _anthropic_resp(stop_reason="max_tokens")
        if adapter_id == "anthropic"
        else _openai_resp(finish_reason="length")
    )


# ── provider factory ──────────────────────────────────────────────────────────

_NO_RETRY = RetryConfig(max_retries=0, backoff_ms=0)


def _make_provider(adapter_id: str, response: httpx.Response | None = None) -> Any:
    resp = response or _default_resp(adapter_id)
    client: MagicMock = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=resp)
    if adapter_id == "openai":
        return OpenAIProvider(
            api_key="sk-test",  # pragma: allowlist secret
            _http_client=client,
            retry_config=_NO_RETRY,
        )
    if adapter_id == "azure_openai":
        return AzureOpenAIProvider(
            resource="test-resource",
            api_key="az-key",  # pragma: allowlist secret
            deployment_chat="chat",
            deployment_extract="extract",
            _http_client=client,
            retry_config=_NO_RETRY,
        )
    if adapter_id == "anthropic":
        return AnthropicProvider(
            api_key="sk-ant-test",  # pragma: allowlist secret
            _http_client=client,
            retry_config=_NO_RETRY,
        )
    if adapter_id == "local":
        return LocalProvider(
            model="mistral:7b",
            _http_client=client,
            retry_config=_NO_RETRY,
        )
    raise ValueError(f"unknown adapter: {adapter_id}")


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── C-LLM-001 Stable identifier ───────────────────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c001_adapter_id_in_valid_set(adapter_id: str) -> None:
    assert _make_provider(adapter_id).id in _VALID_IDS


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c001_version_is_semver(adapter_id: str) -> None:
    parts = _make_provider(adapter_id).version.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)


# ── C-LLM-002 Text round-trip ─────────────────────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c002_text_round_trip(adapter_id: str) -> None:
    result = _run(_make_provider(adapter_id)._do_complete(_CTX, _REQ))
    assert "OK" in result.text


# ── C-LLM-003 Token usage math ───────────────────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c003_token_usage_math(adapter_id: str) -> None:
    result = _run(_make_provider(adapter_id)._do_complete(_CTX, _REQ))
    assert result.usage.total_tokens == result.usage.input_tokens + result.usage.output_tokens


# ── C-LLM-004 Non-zero token counts ──────────────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c004_nonzero_token_counts(adapter_id: str) -> None:
    resp = _default_resp(adapter_id, input_tokens=8, output_tokens=3)
    result = _run(_make_provider(adapter_id, resp)._do_complete(_CTX, _REQ))
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0


# ── C-LLM-005 Structured output success ──────────────────────────────────────


class _Schema(BaseModel):
    value: str


def _structured_resp(adapter_id: str) -> httpx.Response:
    if adapter_id == "anthropic":
        body = {
            "model": "claude-haiku-4-5-20251001",
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "name": "structured_output",
                    "input": {"value": "hello"},
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        return httpx.Response(200, json=body)
    return _openai_resp(text=json.dumps({"value": "hello"}))


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c005_structured_output_success(adapter_id: str) -> None:
    req = LLMRequest(prompt="give me json", schema=_Schema)
    result = _run(_make_provider(adapter_id, _structured_resp(adapter_id))._do_complete(_CTX, req))
    assert isinstance(result.structured, _Schema)
    assert result.structured.value == "hello"


# ── C-LLM-006 Structured output failure is typed ─────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c006_structured_output_violation(adapter_id: str) -> None:
    req = LLMRequest(prompt="give me json", schema=_Schema)
    with pytest.raises(LLMSchemaViolation):
        _run(
            _make_provider(adapter_id, _default_resp(adapter_id, text="not json"))._do_complete(
                _CTX, req
            )
        )


# ── C-LLM-007 Auth failure ────────────────────────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c007_auth_failure_raises(adapter_id: str) -> None:
    provider = _make_provider(adapter_id, httpx.Response(401))
    with pytest.raises(LLMAuthenticationFailed) as exc_info:
        _run(provider._do_complete(_CTX, _REQ))
    assert provider.id in str(exc_info.value)


# ── C-LLM-008 Rate limit is typed and retryable ───────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c008_rate_limit_raises(adapter_id: str) -> None:
    with pytest.raises(LLMRateLimited):
        _run(_make_provider(adapter_id, httpx.Response(429))._do_complete(_CTX, _REQ))


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c008_rate_limit_retried(adapter_id: str, span_exporter: Any) -> None:
    calls = 0
    responses = [httpx.Response(429), _default_resp(adapter_id, text="OK")]

    async def _post(*args: Any, **kwargs: Any) -> httpx.Response:
        nonlocal calls
        resp = responses[calls]
        calls += 1
        return resp

    mock_client: MagicMock = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = _post
    cfg = RetryConfig(max_retries=1, backoff_ms=0)

    if adapter_id == "openai":
        provider = OpenAIProvider(
            api_key="sk-test",  # pragma: allowlist secret
            _http_client=mock_client,
            retry_config=cfg,
        )
    elif adapter_id == "azure_openai":
        provider = AzureOpenAIProvider(
            resource="test-resource",
            api_key="az-key",  # pragma: allowlist secret
            deployment_chat="chat",
            deployment_extract="extract",
            _http_client=mock_client,
            retry_config=cfg,
        )
    elif adapter_id == "anthropic":
        provider = AnthropicProvider(
            api_key="sk-ant-test",  # pragma: allowlist secret
            _http_client=mock_client,
            retry_config=cfg,
        )
    else:
        provider = LocalProvider(model="mistral:7b", _http_client=mock_client, retry_config=cfg)

    result = _run(provider.complete(_CTX, _REQ))
    assert "OK" in result.text
    assert calls == 2
    spans = span_exporter.get_finished_spans()
    assert spans
    assert spans[-1].attributes.get("llm.retry_count") == 1


# ── C-LLM-009 Context window exceeded (output truncation) ────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c009_output_truncation_raises(adapter_id: str) -> None:
    with pytest.raises(LLMContextWindowExceeded):
        _run(_make_provider(adapter_id, _truncation_resp(adapter_id))._do_complete(_CTX, _REQ))


# ── C-LLM-010 Adapter id in response ─────────────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c010_adapter_id_in_response(adapter_id: str) -> None:
    provider = _make_provider(adapter_id)
    result = _run(provider._do_complete(_CTX, _REQ))
    assert result.adapter_id == provider.id


# ── C-LLM-011 OTEL span attributes ───────────────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c011_span_carries_tenant_and_adapter(adapter_id: str, span_exporter: Any) -> None:
    provider = _make_provider(adapter_id)
    _run(provider.complete(_CTX, _REQ))
    spans = span_exporter.get_finished_spans()
    assert spans, "no spans captured"
    attrs = spans[-1].attributes or {}
    assert attrs.get("llm.tenant_id") == _CTX.tenant_id
    assert attrs.get("llm.adapter_id") == provider.id


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c011_span_carries_result_attributes(adapter_id: str, span_exporter: Any) -> None:
    _run(_make_provider(adapter_id).complete(_CTX, _REQ))
    spans = span_exporter.get_finished_spans()
    assert spans
    attrs = spans[-1].attributes or {}
    for key in (
        "llm.model",
        "llm.input_tokens",
        "llm.output_tokens",
        "llm.latency_ms",
        "llm.structured_output_used",
    ):
        assert key in attrs, f"missing span attribute: {key}"


# ── C-LLM-LOCAL-001 No outbound network ──────────────────────────────────────


def test_c_llm_local_001_no_outbound_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _deny(*a: object, **k: object) -> None:
        raise AssertionError("local adapter attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", _deny)
    result = _run(_make_provider("local")._do_complete(_CTX, _REQ))
    assert result.adapter_id == "local"
