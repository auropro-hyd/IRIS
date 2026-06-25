"""Unit tests for iris-adapter-llm-anthropic."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from iris_adapter_llm_anthropic import AnthropicProvider
from iris_adapter_llm_shared.retry import RetryConfig
from iris_engine.contracts.llm_provider import (
    LLMAuthenticationFailed,
    LLMContentFiltered,
    LLMContextWindowExceeded,
    LLMInvalidRequest,
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

_API_KEY = "sk-ant-test-key"  # pragma: allowlist secret
_MODEL_CHAT = "claude-haiku-4-5-20251001"
_MODEL_EXTRACT = "claude-sonnet-4-6"


def _make_response(
    text: str = "OK",
    model: str = "claude-haiku-4-5-20251001",
    stop_reason: str = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 5,
    status: int = 200,
) -> httpx.Response:
    body = {
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
    return httpx.Response(status, json=body)


def _make_tool_response(
    tool_input: dict[str, Any],
    model: str = "claude-haiku-4-5-20251001",
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> httpx.Response:
    body = {
        "model": model,
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_01",
                "name": "structured_output",
                "input": tool_input,
            }
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
    return httpx.Response(200, json=body)


def _make_content_filter_response(via_type: bool = False) -> httpx.Response:
    error = (
        {"type": "output_blocked", "message": "Output blocked by safety system"}
        if via_type
        else {"type": "invalid_request_error", "message": "Output blocked by content filter policy"}
    )
    return httpx.Response(400, json={"type": "error", "error": error})


def _make_provider(response: httpx.Response | None = None) -> AnthropicProvider:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=response or _make_response())
    return AnthropicProvider(
        api_key=_API_KEY,
        model_chat=_MODEL_CHAT,
        model_extract=_MODEL_EXTRACT,
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
    assert provider.id == "anthropic"


def test_adapter_version_is_semver() -> None:
    provider = _make_provider()
    parts = provider.version.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


# ── auth and headers ──────────────────────────────────────────────────────────


def test_request_headers_use_x_api_key() -> None:
    provider = _make_provider()
    headers = provider._request_headers()
    assert "x-api-key" in headers
    assert headers["x-api-key"] == _API_KEY
    assert "Authorization" not in headers


def test_request_headers_include_anthropic_version() -> None:
    provider = _make_provider()
    headers = provider._request_headers()
    assert "anthropic-version" in headers
    assert headers["anthropic-version"] == "2023-06-01"


# ── model hint routing ────────────────────────────────────────────────────────


def test_model_hint_extraction_uses_extract_model() -> None:
    provider = _make_provider()
    assert provider._model_for_hint("extraction") == _MODEL_EXTRACT


def test_model_hint_chat_uses_chat_model() -> None:
    provider = _make_provider()
    assert provider._model_for_hint("chat") == _MODEL_CHAT


def test_model_hint_none_uses_chat_model() -> None:
    provider = _make_provider()
    assert provider._model_for_hint(None) == _MODEL_CHAT


def test_model_hint_summary_uses_chat_model() -> None:
    provider = _make_provider()
    assert provider._model_for_hint("summary") == _MODEL_CHAT


# ── C-LLM-002 Text round-trip ─────────────────────────────────────────────────


def test_complete_text_round_trip() -> None:
    provider = _make_provider(_make_response(text="OK"))
    result = _run(provider._do_complete(_CTX, _REQ))
    assert "OK" in result.text
    assert result.adapter_id == "anthropic"


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


# ── C-LLM-005 Structured output (tool use) ───────────────────────────────────


class _Schema(BaseModel):
    value: str


def test_structured_output_success() -> None:
    provider = _make_provider(_make_tool_response({"value": "hello"}))
    req = LLMRequest(prompt="give me json", schema=_Schema)
    result = _run(provider._do_complete(_CTX, req))
    assert isinstance(result.structured, _Schema)
    assert result.structured.value == "hello"


def test_structured_output_text_is_json_of_tool_input() -> None:
    provider = _make_provider(_make_tool_response({"value": "world"}))
    req = LLMRequest(prompt="give me json", schema=_Schema)
    result = _run(provider._do_complete(_CTX, req))
    parsed = json.loads(result.text)
    assert parsed["value"] == "world"


# ── C-LLM-006 Structured output failure ──────────────────────────────────────


def test_structured_output_missing_tool_block_raises_violation() -> None:
    # tool use requested but response has only text block - schema violation
    provider = _make_provider(_make_response(text="not json"))
    req = LLMRequest(prompt="give me json", schema=_Schema)
    with pytest.raises(LLMSchemaViolation):
        _run(provider._do_complete(_CTX, req))


def test_structured_output_invalid_tool_input_raises_violation() -> None:
    provider = _make_provider(_make_tool_response({"wrong_field": "oops"}))
    req = LLMRequest(prompt="give me json", schema=_Schema)
    with pytest.raises(LLMSchemaViolation):
        _run(provider._do_complete(_CTX, req))


def test_structured_output_null_tool_input_raises_violation() -> None:
    body = {
        "model": "claude-haiku-4-5-20251001",
        "content": [{"type": "tool_use", "id": "t1", "name": "structured_output", "input": None}],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    provider = _make_provider(httpx.Response(200, json=body))
    req = LLMRequest(prompt="give me json", schema=_Schema)
    with pytest.raises(LLMSchemaViolation, match="null"):
        _run(provider._do_complete(_CTX, req))


# ── C-LLM-007 Auth failure ────────────────────────────────────────────────────


def test_auth_failure_raises_typed_error() -> None:
    provider = _make_provider(httpx.Response(401))
    with pytest.raises(LLMAuthenticationFailed, match="anthropic"):
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
    provider = AnthropicProvider(
        api_key=_API_KEY,
        retry_config=RetryConfig(max_retries=1, backoff_ms=0),
        _http_client=mock_client,
    )
    result = _run(provider.complete(_CTX, _REQ))
    assert "OK" in result.text
    assert calls == 2


# ── C-LLM-009 Context window ─────────────────────────────────────────────────


def test_max_tokens_stop_reason_raises_context_window() -> None:
    provider = _make_provider(_make_response(stop_reason="max_tokens"))
    with pytest.raises(LLMContextWindowExceeded, match="anthropic") as exc_info:
        _run(provider._do_complete(_CTX, _REQ))
    msg = str(exc_info.value).lower()
    assert "truncated" in msg or "max output tokens" in msg


# ── C-LLM-010 Adapter id in response ─────────────────────────────────────────


def test_adapter_id_in_response() -> None:
    provider = _make_provider()
    result = _run(provider._do_complete(_CTX, _REQ))
    assert result.adapter_id == provider.id


# ── content filter ────────────────────────────────────────────────────────────


def test_content_filter_raises_via_message() -> None:
    provider = _make_provider(_make_content_filter_response(via_type=False))
    with pytest.raises(LLMContentFiltered):
        _run(provider._do_complete(_CTX, _REQ))


def test_content_filter_raises_via_error_type() -> None:
    provider = _make_provider(_make_content_filter_response(via_type=True))
    with pytest.raises(LLMContentFiltered):
        _run(provider._do_complete(_CTX, _REQ))


# ── empty content list ────────────────────────────────────────────────────────


def test_empty_content_list_raises_unavailable() -> None:
    body = {
        "model": "claude-haiku-4-5-20251001",
        "content": [],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 0},
    }
    provider = _make_provider(httpx.Response(200, json=body))
    with pytest.raises(LLMUnavailable, match="empty response"):
        _run(provider._do_complete(_CTX, _REQ))


# ── 400 bad request (non-filter) ─────────────────────────────────────────────


def test_bad_request_raises_invalid_request() -> None:
    body = {"type": "error", "error": {"type": "invalid_request_error", "message": "bad param"}}
    provider = _make_provider(httpx.Response(400, json=body))
    with pytest.raises(LLMInvalidRequest):
        _run(provider._do_complete(_CTX, _REQ))


# ── network errors ────────────────────────────────────────────────────────────


def test_timeout_raises_unavailable() -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    provider = AnthropicProvider(api_key=_API_KEY, _http_client=mock_client)
    with pytest.raises(LLMUnavailable, match="timed out"):
        _run(provider._do_complete(_CTX, _REQ))


def test_connect_error_raises_unavailable() -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    provider = AnthropicProvider(api_key=_API_KEY, _http_client=mock_client)
    with pytest.raises(LLMUnavailable, match="connection failed"):
        _run(provider._do_complete(_CTX, _REQ))


# ── Anthropic-specific: system prompt ────────────────────────────────────────


def test_system_prompt_is_sent_in_body() -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_make_response())
    provider = AnthropicProvider(api_key=_API_KEY, _http_client=mock_client)
    req = LLMRequest(prompt="hi", system="You are a test assistant.")
    _run(provider._do_complete(_CTX, req))
    _, kwargs = mock_client.post.call_args
    body = kwargs.get("json", {})
    assert body.get("system") == "You are a test assistant."


# ── from_env ──────────────────────────────────────────────────────────────────


def test_from_env_raises_on_missing_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IRIS_LLM_ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="IRIS_LLM_ANTHROPIC_API_KEY"):
        AnthropicProvider.from_env()
