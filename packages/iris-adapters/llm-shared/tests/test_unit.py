"""Unit tests for iris-llm-shared: retry helper and OpenAI-compat base class."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from iris_adapter_llm_shared.openai_compat import OpenAICompatProvider, _raise_for_status
from iris_adapter_llm_shared.retry import RetryConfig, with_retry
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
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
        },
    }
    return httpx.Response(status, json=body)


class _StubProvider(OpenAICompatProvider):
    """Minimal concrete subclass for testing the base class."""

    @property
    def id(self) -> str:
        return "openai"

    def _base_url(self) -> str:
        return "https://api.openai.com/v1/chat/completions"

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer sk-test"}


def _make_provider(response: httpx.Response | None = None) -> _StubProvider:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=response or _make_response())
    return _StubProvider(_http_client=mock_client)


def _run(coro: Any) -> Any:
    return asyncio.new_event_loop().run_until_complete(coro)


# ── RetryConfig ───────────────────────────────────────────────────────────────


def test_retry_config_defaults() -> None:
    cfg = RetryConfig()
    assert cfg.max_retries == 3
    assert cfg.backoff_ms == 500


def test_retry_config_from_params() -> None:
    cfg = RetryConfig.from_params(max_retries=5, retry_backoff_ms=250)
    assert cfg.max_retries == 5
    assert cfg.backoff_ms == 250


# ── with_retry ────────────────────────────────────────────────────────────────


def test_with_retry_succeeds_on_first_attempt() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result, retry_count = _run(with_retry(fn, RetryConfig(max_retries=3, backoff_ms=0)))
    assert result == "ok"
    assert calls == 1
    assert retry_count == 0


def test_with_retry_retries_on_rate_limited() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise LLMRateLimited("429")
        return "ok"

    result, retry_count = _run(with_retry(fn, RetryConfig(max_retries=3, backoff_ms=0)))
    assert result == "ok"
    assert calls == 3
    assert retry_count == 2


def test_with_retry_retries_on_unavailable() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise LLMUnavailable("503")
        return "ok"

    result, retry_count = _run(with_retry(fn, RetryConfig(max_retries=2, backoff_ms=0)))
    assert result == "ok"
    assert calls == 2
    assert retry_count == 1


def test_with_retry_raises_after_max_retries() -> None:
    async def fn() -> str:
        raise LLMRateLimited("always 429")

    with pytest.raises(LLMRateLimited):
        _run(with_retry(fn, RetryConfig(max_retries=2, backoff_ms=0)))


def test_with_retry_does_not_retry_other_errors() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        raise LLMAuthenticationFailed("401")

    with pytest.raises(LLMAuthenticationFailed):
        _run(with_retry(fn, RetryConfig(max_retries=3, backoff_ms=0)))
    assert calls == 1


# ── _raise_for_status ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("status", [401, 403])
def test_raise_for_status_auth_failed(status: int) -> None:
    resp = httpx.Response(status)
    with pytest.raises(LLMAuthenticationFailed, match="openai"):
        _raise_for_status(resp, "openai")


def test_raise_for_status_rate_limited() -> None:
    resp = httpx.Response(429)
    with pytest.raises(LLMRateLimited):
        _raise_for_status(resp, "openai")


def test_raise_for_status_bad_request() -> None:
    resp = httpx.Response(400)
    with pytest.raises(LLMInvalidRequest):
        _raise_for_status(resp, "openai")


def test_raise_for_status_server_error() -> None:
    resp = httpx.Response(503)
    with pytest.raises(LLMUnavailable):
        _raise_for_status(resp, "openai")


def test_raise_for_status_ok_is_noop() -> None:
    resp = httpx.Response(200)
    _raise_for_status(resp, "openai")  # no exception


# ── OpenAICompatProvider._do_complete ─────────────────────────────────────────


def test_complete_text_round_trip() -> None:
    provider = _make_provider(_make_response(text="OK"))
    result = _run(provider._do_complete(_CTX, _REQ))
    assert "OK" in result.text
    assert result.adapter_id == "openai"
    assert result.model == "gpt-4o-mini"


def test_complete_usage_math() -> None:
    provider = _make_provider(_make_response(input_tokens=10, output_tokens=5))
    result = _run(provider._do_complete(_CTX, _REQ))
    assert result.usage.total_tokens == result.usage.input_tokens + result.usage.output_tokens


def test_complete_adapter_id_in_response() -> None:
    provider = _make_provider()
    result = _run(provider._do_complete(_CTX, _REQ))
    assert result.adapter_id == provider.id


def test_complete_content_filter_raises() -> None:
    provider = _make_provider(_make_response(finish_reason="content_filter"))
    with pytest.raises(LLMContentFiltered):
        _run(provider._do_complete(_CTX, _REQ))


def test_complete_length_raises_context_window() -> None:
    provider = _make_provider(_make_response(finish_reason="length"))
    with pytest.raises(LLMContextWindowExceeded):
        _run(provider._do_complete(_CTX, _REQ))


def test_complete_auth_failure_raises() -> None:
    provider = _make_provider(httpx.Response(401))
    with pytest.raises(LLMAuthenticationFailed, match="openai"):
        _run(provider._do_complete(_CTX, _REQ))


def test_complete_auth_error_does_not_leak_key() -> None:
    provider = _make_provider(httpx.Response(401))
    with pytest.raises(LLMAuthenticationFailed) as exc_info:
        _run(provider._do_complete(_CTX, _REQ))
    assert "sk-test" not in str(exc_info.value)


def test_complete_rate_limit_raises() -> None:
    provider = _make_provider(httpx.Response(429))
    with pytest.raises(LLMRateLimited):
        _run(provider._do_complete(_CTX, _REQ))


def test_complete_server_error_raises_unavailable() -> None:
    provider = _make_provider(httpx.Response(503))
    with pytest.raises(LLMUnavailable):
        _run(provider._do_complete(_CTX, _REQ))


def test_complete_timeout_raises_unavailable() -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    provider = _StubProvider(_http_client=mock_client)
    with pytest.raises(LLMUnavailable, match="timed out"):
        _run(provider._do_complete(_CTX, _REQ))


def test_complete_connect_error_raises_unavailable() -> None:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    provider = _StubProvider(_http_client=mock_client)
    with pytest.raises(LLMUnavailable, match="connection failed"):
        _run(provider._do_complete(_CTX, _REQ))


# ── structured output ─────────────────────────────────────────────────────────


class _Schema(BaseModel):
    value: str


def test_complete_structured_output_success() -> None:
    payload = json.dumps({"value": "hello"})
    provider = _make_provider(_make_response(text=payload))
    req = LLMRequest(prompt="give me json", schema=_Schema)
    result = _run(provider._do_complete(_CTX, req))
    assert isinstance(result.structured, _Schema)
    assert result.structured.value == "hello"


def test_complete_structured_output_violation() -> None:
    provider = _make_provider(_make_response(text="not json at all"))
    req = LLMRequest(prompt="give me json", schema=_Schema)
    with pytest.raises(LLMSchemaViolation, match="_Schema"):
        _run(provider._do_complete(_CTX, req))


def test_complete_no_schema_structured_is_none() -> None:
    provider = _make_provider(_make_response(text="plain text"))
    result = _run(provider._do_complete(_CTX, _REQ))
    assert result.structured is None


# ── span attributes ───────────────────────────────────────────────────────────


def test_retry_count_zero_on_span_when_no_retries(span_exporter: Any) -> None:
    provider = _make_provider(_make_response(text="OK"))
    _run(provider.complete(_CTX, _REQ))
    spans = span_exporter.get_finished_spans()
    assert spans, "no spans captured"
    attrs = spans[-1].attributes or {}
    assert attrs.get("llm.retry_count") == 0


def test_retry_count_one_on_span_after_one_retry(span_exporter: Any) -> None:
    calls = 0
    responses = [httpx.Response(429), _make_response(text="OK")]

    async def _post(*args: Any, **kwargs: Any) -> httpx.Response:
        nonlocal calls
        resp = responses[calls]
        calls += 1
        return resp

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = _post
    provider = _StubProvider(
        retry_config=RetryConfig(max_retries=1, backoff_ms=0),
        _http_client=mock_client,
    )
    result = _run(provider.complete(_CTX, _REQ))
    assert "OK" in result.text
    spans = span_exporter.get_finished_spans()
    assert spans, "no spans captured"
    attrs = spans[-1].attributes or {}
    assert attrs.get("llm.retry_count") == 1
