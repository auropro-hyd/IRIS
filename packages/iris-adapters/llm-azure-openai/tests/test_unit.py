"""Unit tests for iris-llm-azure-openai."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from iris_adapter_llm_azure_openai import AzureOpenAIProvider
from iris_adapter_llm_shared.retry import RetryConfig
from iris_engine.contracts.llm_provider import (
    LLMAuthenticationFailed,
    LLMContentFiltered,
    LLMContextWindowExceeded,
    LLMRateLimited,
    LLMRequest,
    LLMSchemaViolation,
    LLMUnavailable,
    TenantContext,
)
from pydantic import BaseModel

# ── fixtures ──────────────────────────────────────────────────────────────────

_CTX = TenantContext(tenant_id="test-tenant", product_slug="test/in")
_REQ = LLMRequest(prompt="Reply with the single word OK")

_RESOURCE = "my-resource"
_API_KEY = "secret-key"  # pragma: allowlist secret
_CHAT_DEPLOY = "gpt-4o-mini-chat"
_EXTRACT_DEPLOY = "gpt-4o-extract"
_API_VERSION = "2024-02-01"


def _make_response(
    text: str = "OK",
    model: str = "gpt-4o-mini",
    finish_reason: str = "stop",
    input_tokens: int = 10,
    output_tokens: int = 5,
    status: int = 200,
) -> httpx.Response:
    body = {
        "model": model,
        "choices": [{"message": {"content": text}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
    }
    return httpx.Response(status, json=body)


def _make_provider(response: httpx.Response | None = None) -> AzureOpenAIProvider:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=response or _make_response())
    return AzureOpenAIProvider(
        resource=_RESOURCE,
        api_key=_API_KEY,
        deployment_chat=_CHAT_DEPLOY,
        deployment_extract=_EXTRACT_DEPLOY,
        api_version=_API_VERSION,
        retry_config=RetryConfig(max_retries=0, backoff_ms=0),
        _http_client=mock_client,
    )


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── C-LLM-001 Stable identifier ───────────────────────────────────────────────


def test_adapter_id() -> None:
    provider = _make_provider()
    assert provider.id == "azure-openai"


def test_adapter_version_is_semver() -> None:
    provider = _make_provider()
    parts = provider.version.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


# ── URL construction ──────────────────────────────────────────────────────────


def test_base_url_uses_chat_deployment_by_default() -> None:
    provider = _make_provider()
    url = provider._base_url()
    assert _CHAT_DEPLOY in url
    assert _RESOURCE in url
    assert _API_VERSION in url


def test_model_hint_extract_switches_deployment() -> None:
    provider = _make_provider()
    provider._model_for_hint("extraction", "")
    url = provider._base_url()
    assert _EXTRACT_DEPLOY in url


def test_model_hint_chat_uses_chat_deployment() -> None:
    provider = _make_provider()
    provider._model_for_hint("chat", "")
    url = provider._base_url()
    assert _CHAT_DEPLOY in url


def test_model_hint_none_uses_chat_deployment() -> None:
    provider = _make_provider()
    provider._model_for_hint(None, "")
    url = provider._base_url()
    assert _CHAT_DEPLOY in url


def test_url_contains_api_version() -> None:
    provider = _make_provider()
    assert f"api-version={_API_VERSION}" in provider._base_url()


# ── Auth headers ──────────────────────────────────────────────────────────────


def test_auth_header_is_api_key_not_bearer() -> None:
    provider = _make_provider()
    headers = provider._auth_headers()
    assert "api-key" in headers
    assert headers["api-key"] == _API_KEY
    assert "Authorization" not in headers


# ── C-LLM-002 Text round-trip ─────────────────────────────────────────────────


def test_complete_text_round_trip() -> None:
    provider = _make_provider(_make_response(text="OK"))
    result = _run(provider._do_complete(_CTX, _REQ))
    assert "OK" in result.text
    assert result.adapter_id == "azure-openai"


# ── C-LLM-003 Token usage math ───────────────────────────────────────────────


def test_token_usage_math() -> None:
    provider = _make_provider(_make_response(input_tokens=10, output_tokens=5))
    result = _run(provider._do_complete(_CTX, _REQ))
    assert result.usage.total_tokens == result.usage.input_tokens + result.usage.output_tokens


# ── C-LLM-004 Non-zero token counts ──────────────────────────────────────────


def test_non_zero_token_counts() -> None:
    provider = _make_provider(_make_response(input_tokens=8, output_tokens=3))
    result = _run(provider._do_complete(_CTX, _REQ))
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0


# ── C-LLM-005 Structured output ──────────────────────────────────────────────


class _Schema(BaseModel):
    value: str


def test_structured_output_success() -> None:
    payload = json.dumps({"value": "hello"})
    provider = _make_provider(_make_response(text=payload))
    req = LLMRequest(prompt="give me json", schema=_Schema)
    result = _run(provider._do_complete(_CTX, req))
    assert isinstance(result.structured, _Schema)
    assert result.structured.value == "hello"


# ── C-LLM-006 Structured output failure ──────────────────────────────────────


def test_structured_output_violation() -> None:
    provider = _make_provider(_make_response(text="not json"))
    req = LLMRequest(prompt="give me json", schema=_Schema)
    with pytest.raises(LLMSchemaViolation):
        _run(provider._do_complete(_CTX, req))


# ── C-LLM-007 Auth failure ────────────────────────────────────────────────────


def test_auth_failure_raises_typed_error() -> None:
    provider = _make_provider(httpx.Response(401))
    with pytest.raises(LLMAuthenticationFailed, match="azure-openai"):
        _run(provider._do_complete(_CTX, _REQ))


def test_auth_error_does_not_leak_key() -> None:
    provider = _make_provider(httpx.Response(401))
    with pytest.raises(LLMAuthenticationFailed) as exc_info:
        _run(provider._do_complete(_CTX, _REQ))
    assert _API_KEY not in str(exc_info.value)


# ── C-LLM-008 Rate limit ─────────────────────────────────────────────────────


def test_rate_limit_raises() -> None:
    provider = _make_provider(httpx.Response(429))
    with pytest.raises(LLMRateLimited):
        _run(provider._do_complete(_CTX, _REQ))


def test_rate_limit_is_retried() -> None:
    calls = 0
    responses = [httpx.Response(429), _make_response(text="OK")]

    async def _post(*args: Any, **kwargs: Any) -> httpx.Response:
        nonlocal calls
        resp = responses[calls]
        calls += 1
        return resp

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = _post
    provider = AzureOpenAIProvider(
        resource=_RESOURCE,
        api_key=_API_KEY,
        deployment_chat=_CHAT_DEPLOY,
        deployment_extract=_EXTRACT_DEPLOY,
        retry_config=RetryConfig(max_retries=1, backoff_ms=0),
        _http_client=mock_client,
    )
    result = _run(provider.complete(_CTX, _REQ))
    assert "OK" in result.text
    assert calls == 2


# ── C-LLM-009 Context window ─────────────────────────────────────────────────


def test_length_finish_reason_raises_context_window() -> None:
    provider = _make_provider(_make_response(finish_reason="length"))
    with pytest.raises(LLMContextWindowExceeded):
        _run(provider._do_complete(_CTX, _REQ))


# ── C-LLM-010 Adapter id in response ─────────────────────────────────────────


def test_adapter_id_in_response() -> None:
    provider = _make_provider()
    result = _run(provider._do_complete(_CTX, _REQ))
    assert result.adapter_id == provider.id


# ── content filter ────────────────────────────────────────────────────────────


def test_content_filter_raises() -> None:
    provider = _make_provider(_make_response(finish_reason="content_filter"))
    with pytest.raises(LLMContentFiltered):
        _run(provider._do_complete(_CTX, _REQ))


# ── network errors ────────────────────────────────────────────────────────────


def test_timeout_raises_unavailable() -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    provider = AzureOpenAIProvider(
        resource=_RESOURCE,
        api_key=_API_KEY,
        deployment_chat=_CHAT_DEPLOY,
        deployment_extract=_EXTRACT_DEPLOY,
        _http_client=mock_client,
    )
    with pytest.raises(LLMUnavailable, match="timed out"):
        _run(provider._do_complete(_CTX, _REQ))


def test_connect_error_raises_unavailable() -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    provider = AzureOpenAIProvider(
        resource=_RESOURCE,
        api_key=_API_KEY,
        deployment_chat=_CHAT_DEPLOY,
        deployment_extract=_EXTRACT_DEPLOY,
        _http_client=mock_client,
    )
    with pytest.raises(LLMUnavailable, match="connection failed"):
        _run(provider._do_complete(_CTX, _REQ))


# ── from_env ──────────────────────────────────────────────────────────────────


def test_from_env_raises_on_missing_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IRIS_LLM_AZURE_RESOURCE", raising=False)
    with pytest.raises(RuntimeError, match="IRIS_LLM_AZURE_RESOURCE"):
        AzureOpenAIProvider.from_env()
