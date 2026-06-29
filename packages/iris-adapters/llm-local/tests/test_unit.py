"""Unit tests for iris-adapter-llm-local.

Clauses covered:
  C-LLM-001  Stable identifier (id == "local", semver version)
  C-LLM-002  Text round-trip
  C-LLM-003  Token usage math
  C-LLM-004  Non-zero token counts
  C-LLM-005  Structured output success
  C-LLM-006  Structured output schema violation
  C-LLM-007  Auth failure raises typed error
  C-LLM-008  Rate limit raises and retries
  C-LLM-009  Context window exceeded (output truncation)
  C-LLM-010  Adapter id in response
  C-LLM-LOCAL-001  No outbound network (socket guard)
"""

from __future__ import annotations

import asyncio
import json
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from iris_adapter_llm_local import LocalProvider
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

_MODEL = "mistral:7b"
_API_KEY = "local-secret"  # pragma: allowlist secret


def _make_response(
    text: str = "OK",
    model: str = _MODEL,
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


def _make_provider(response: httpx.Response | None = None) -> LocalProvider:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=response or _make_response())
    return LocalProvider(
        model=_MODEL,
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
    assert _make_provider().id == "local"


def test_adapter_version_is_semver() -> None:
    parts = _make_provider().version.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


# ── URL and auth ──────────────────────────────────────────────────────────────


def test_base_url_default_is_localhost() -> None:
    provider = LocalProvider(model=_MODEL)
    assert provider._base_url() == "http://localhost:8080/v1/chat/completions"


def test_base_url_custom_env(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = LocalProvider(model=_MODEL, base_url="http://localhost:11434/v1")
    assert provider._base_url() == "http://localhost:11434/v1/chat/completions"


def test_auth_header_empty_when_no_key() -> None:
    provider = LocalProvider(model=_MODEL)
    assert provider._auth_headers() == {}


def test_auth_header_bearer_when_key_set() -> None:
    provider = LocalProvider(model=_MODEL, api_key=_API_KEY)
    assert provider._auth_headers() == {"Authorization": f"Bearer {_API_KEY}"}


# ── model hint routing ────────────────────────────────────────────────────────


def test_model_hint_always_returns_configured_model() -> None:
    provider = _make_provider()
    for hint in ("extraction", "chat", "summary", None):
        assert provider._model_for_hint(hint, "") == _MODEL


# ── C-LLM-002 Text round-trip ─────────────────────────────────────────────────


def test_complete_text_round_trip() -> None:
    result = _run(_make_provider(_make_response(text="OK"))._do_complete(_CTX, _REQ))
    assert "OK" in result.text
    assert result.adapter_id == "local"


# ── C-LLM-003 Token usage math ───────────────────────────────────────────────


def test_token_usage_math() -> None:
    result = _run(
        _make_provider(_make_response(input_tokens=10, output_tokens=5))._do_complete(_CTX, _REQ)
    )
    assert result.usage.total_tokens == result.usage.input_tokens + result.usage.output_tokens


# ── C-LLM-004 Non-zero token counts ──────────────────────────────────────────


def test_non_zero_token_counts() -> None:
    result = _run(
        _make_provider(_make_response(input_tokens=8, output_tokens=3))._do_complete(_CTX, _REQ)
    )
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0


# ── C-LLM-005 Structured output ──────────────────────────────────────────────


class _Schema(BaseModel):
    value: str


def test_structured_output_success() -> None:
    payload = json.dumps({"value": "hello"})
    req = LLMRequest(prompt="give me json", schema=_Schema)
    result = _run(_make_provider(_make_response(text=payload))._do_complete(_CTX, req))
    assert isinstance(result.structured, _Schema)
    assert result.structured.value == "hello"


# ── C-LLM-006 Structured output failure ──────────────────────────────────────


def test_structured_output_violation() -> None:
    req = LLMRequest(prompt="give me json", schema=_Schema)
    with pytest.raises(LLMSchemaViolation):
        _run(_make_provider(_make_response(text="not json"))._do_complete(_CTX, req))


# ── C-LLM-007 Auth failure ────────────────────────────────────────────────────


def test_auth_failure_raises_typed_error() -> None:
    with pytest.raises(LLMAuthenticationFailed, match="local"):
        _run(_make_provider(httpx.Response(401))._do_complete(_CTX, _REQ))


def test_auth_error_does_not_leak_key() -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=httpx.Response(401))
    provider = LocalProvider(model=_MODEL, api_key=_API_KEY, _http_client=mock_client)
    with pytest.raises(LLMAuthenticationFailed) as exc_info:
        _run(provider._do_complete(_CTX, _REQ))
    assert _API_KEY not in str(exc_info.value)


# ── C-LLM-008 Rate limit ─────────────────────────────────────────────────────


def test_rate_limit_raises() -> None:
    with pytest.raises(LLMRateLimited):
        _run(_make_provider(httpx.Response(429))._do_complete(_CTX, _REQ))


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
    provider = LocalProvider(
        model=_MODEL,
        retry_config=RetryConfig(max_retries=1, backoff_ms=0),
        _http_client=mock_client,
    )
    result = _run(provider.complete(_CTX, _REQ))
    assert "OK" in result.text
    assert calls == 2


# ── C-LLM-009 Context window ─────────────────────────────────────────────────


def test_length_finish_reason_raises_context_window() -> None:
    with pytest.raises(LLMContextWindowExceeded, match="local") as exc_info:
        _run(_make_provider(_make_response(finish_reason="length"))._do_complete(_CTX, _REQ))
    msg = str(exc_info.value).lower()
    assert "truncated" in msg or "context window" in msg


# ── C-LLM-010 Adapter id in response ─────────────────────────────────────────


def test_adapter_id_in_response() -> None:
    result = _run(_make_provider()._do_complete(_CTX, _REQ))
    assert result.adapter_id == "local"


# ── content filter ────────────────────────────────────────────────────────────


def test_content_filter_raises() -> None:
    with pytest.raises(LLMContentFiltered):
        _run(
            _make_provider(_make_response(finish_reason="content_filter"))._do_complete(_CTX, _REQ)
        )


# ── network errors ────────────────────────────────────────────────────────────


def test_timeout_raises_unavailable() -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    provider = LocalProvider(model=_MODEL, _http_client=mock_client)
    with pytest.raises(LLMUnavailable, match="timed out"):
        _run(provider._do_complete(_CTX, _REQ))


def test_connect_error_raises_unavailable() -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    provider = LocalProvider(model=_MODEL, _http_client=mock_client)
    with pytest.raises(LLMUnavailable, match="connection failed"):
        _run(provider._do_complete(_CTX, _REQ))


# ── from_env ──────────────────────────────────────────────────────────────────


def test_from_env_raises_on_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IRIS_LLM_LOCAL_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="IRIS_LLM_LOCAL_MODEL"):
        LocalProvider.from_env()


# ── C-LLM-LOCAL-001 No outbound network access ───────────────────────────────
# Verifies the adapter completes successfully with all non-localhost sockets
# blocked. The injected mock httpx client opens no real sockets; the guard
# ensures no secondary network call escapes the mocked path.


def test_c_llm_local_001_no_outbound_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _deny(*a: object, **k: object) -> None:
        raise AssertionError("local adapter attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", _deny)
    result = _run(_make_provider(_make_response(text="OK"))._do_complete(_CTX, _REQ))
    assert result.adapter_id == "local"
