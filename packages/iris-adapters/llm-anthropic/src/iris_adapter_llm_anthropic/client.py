"""Anthropic Messages API LLM adapter.

Standalone implementation - does not inherit OpenAICompatProvider.
Authentication: x-api-key header + anthropic-version header.
Endpoint: https://api.anthropic.com/v1/messages
Structured output: Anthropic tool-use pattern (not JSON mode).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, cast

import httpx
from iris_adapter_llm_shared.env import require_env
from iris_adapter_llm_shared.retry import RetryConfig, with_retry
from iris_engine.contracts.llm_provider import (
    LLMAuthenticationFailed,
    LLMContentFiltered,
    LLMContextWindowExceeded,
    LLMInvalidRequest,
    LLMRateLimited,
    LLMRequest,
    LLMResponse,
    LLMSchemaViolation,
    LLMUnavailable,
    LLMUsage,
    TenantContext,
)
from iris_engine.llm.tracing import instrument_complete, log_complete_success
from pydantic import BaseModel, ValidationError

_ANTHROPIC_VERSION = "2023-06-01"
_BASE_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider:
    """LLM adapter for the Anthropic Messages API."""

    version: str = "1.0.0"

    @property
    def id(self) -> str:
        return "anthropic"

    def __init__(
        self,
        api_key: str,
        model_chat: str = _DEFAULT_MODEL,
        model_extract: str = _DEFAULT_MODEL,
        *,
        retry_config: RetryConfig | None = None,
        _http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model_chat = model_chat
        self._model_extract = model_extract
        self._retry_config = retry_config or RetryConfig()
        self._http_client = _http_client

    @classmethod
    def from_env(cls, retry_config: RetryConfig | None = None) -> AnthropicProvider:
        """Construct from environment variables.

        Required:
            IRIS_LLM_ANTHROPIC_API_KEY    Anthropic API key (sk-ant-...)

        Optional:
            IRIS_LLM_ANTHROPIC_MODEL_CHAT     Model for chat/classify/summarise
            IRIS_LLM_ANTHROPIC_MODEL_EXTRACT  Model for extraction calls
        """
        return cls(
            api_key=require_env("IRIS_LLM_ANTHROPIC_API_KEY"),
            model_chat=os.environ.get("IRIS_LLM_ANTHROPIC_MODEL_CHAT", _DEFAULT_MODEL),
            model_extract=os.environ.get("IRIS_LLM_ANTHROPIC_MODEL_EXTRACT", _DEFAULT_MODEL),
            retry_config=retry_config,
        )

    def _model_for_hint(self, hint: str | None) -> str:
        if hint == "extraction":
            return self._model_extract
        return self._model_chat

    def _request_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    async def complete(
        self,
        ctx: TenantContext,
        request: LLMRequest,
    ) -> LLMResponse:
        async with instrument_complete(self.id, ctx, request) as span:
            result, retry_count = await with_retry(
                lambda: self._do_complete(ctx, request),
                self._retry_config,
            )
            span.set_attribute("llm.model", result.model)
            span.set_attribute("llm.input_tokens", result.usage.input_tokens)
            span.set_attribute("llm.output_tokens", result.usage.output_tokens)
            span.set_attribute("llm.latency_ms", result.latency_ms)
            span.set_attribute("llm.structured_output_used", result.structured is not None)
            span.set_attribute("llm.retry_count", retry_count)
            log_complete_success(self.id, ctx, result)
            return result

    async def _do_complete(
        self,
        ctx: TenantContext,
        request: LLMRequest,
    ) -> LLMResponse:
        model = self._model_for_hint(request.model_hint)
        body = _build_request_body(model, request)

        start = time.monotonic()
        if self._http_client is not None:
            response = await self._call(self._http_client, body)
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await self._call(client, body)
        latency_ms = int((time.monotonic() - start) * 1000)

        data = _parse_response(response, self.id)
        return _map_result(data, self.id, model, latency_ms, request.schema)

    async def _call(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
    ) -> httpx.Response:
        try:
            response = await client.post(
                _BASE_URL,
                json=body,
                headers=self._request_headers(),
            )
        except httpx.TimeoutException as exc:
            raise LLMUnavailable(f"[{self.id}] request timed out") from exc
        except httpx.ConnectError as exc:
            raise LLMUnavailable(f"[{self.id}] connection failed") from exc
        _raise_for_status(response, self.id)
        return response


# ── helpers ───────────────────────────────────────────────────────────────────


def _build_request_body(model: str, request: LLMRequest) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": request.prompt}],
        "max_tokens": (
            request.max_output_tokens
            if request.max_output_tokens is not None
            else _DEFAULT_MAX_TOKENS
        ),
        "temperature": request.temperature,
    }
    if request.system:
        body["system"] = request.system
    if request.stop:
        body["stop_sequences"] = request.stop
    if request.schema is not None:
        body["tools"] = [
            {
                "name": "structured_output",
                "description": "Return the requested structured data.",
                "input_schema": request.schema.model_json_schema(),
            }
        ]
        body["tool_choice"] = {"type": "tool", "name": "structured_output"}
    return body


def _parse_response(response: httpx.Response, adapter_id: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], response.json())
    except Exception as exc:
        raise LLMUnavailable(f"[{adapter_id}] non-JSON response from provider") from exc


def _map_result(
    data: dict[str, Any],
    adapter_id: str,
    model: str,
    latency_ms: int,
    schema: type[BaseModel] | None,
) -> LLMResponse:
    try:
        content_blocks: list[dict[str, Any]] = data["content"]
        usage_data: dict[str, int] = data.get("usage", {})
        input_tokens = int(usage_data.get("input_tokens", 0))
        output_tokens = int(usage_data.get("output_tokens", 0))
        stop_reason: str = data.get("stop_reason", "")
    except (KeyError, TypeError) as exc:
        raise LLMUnavailable(f"[{adapter_id}] unexpected response shape: {exc}") from exc

    if stop_reason == "max_tokens":
        raise LLMContextWindowExceeded(
            f"[{adapter_id}] response truncated: max output tokens reached"
        )

    text = ""
    tool_input: dict[str, Any] | None = None
    tool_use_found = False
    for block in content_blocks:
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text", "")
        elif block_type == "tool_use" and block.get("name") == "structured_output":
            tool_use_found = True
            tool_input = cast(dict[str, Any], block.get("input"))

    if not text and not tool_use_found:
        raise LLMUnavailable(f"[{adapter_id}] empty response: no content blocks returned")

    structured: BaseModel | None = None
    if schema is not None:
        if not tool_use_found:
            raise LLMSchemaViolation(
                f"[{adapter_id}] structured output did not match {schema.__name__}: "
                "tool_use block missing from response"
            )
        if tool_input is None:
            raise LLMSchemaViolation(
                f"[{adapter_id}] structured output did not match {schema.__name__}: "
                "tool_use block input was null"
            )
        try:
            structured = schema.model_validate(tool_input)
        except (ValidationError, ValueError) as exc:
            raise LLMSchemaViolation(
                f"[{adapter_id}] structured output did not match {schema.__name__}: {exc}"
            ) from exc
        text = json.dumps(tool_input)

    return LLMResponse(
        text=text,
        structured=structured,
        model=data.get("model", model),
        adapter_id=adapter_id,
        usage=LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        latency_ms=latency_ms,
    )


_CONTENT_FILTER_TYPES: frozenset[str] = frozenset(
    {"output_blocked", "content_policy_violation", "content_filter"}
)
_CONTENT_FILTER_KEYWORDS: tuple[str, ...] = ("filter", "block", "policy", "safety")


def _is_content_filter_error(err: dict[str, Any]) -> bool:
    if str(err.get("type", "")) in _CONTENT_FILTER_TYPES:
        return True
    msg = str(err.get("message", "")).lower()
    return any(kw in msg for kw in _CONTENT_FILTER_KEYWORDS)


def _raise_for_status(response: httpx.Response, adapter_id: str) -> None:
    status = response.status_code
    if status in {401, 403}:
        raise LLMAuthenticationFailed(f"[{adapter_id}] authentication failed: HTTP {status}")
    if status == 429:
        raise LLMRateLimited(f"[{adapter_id}] rate limit exceeded")
    if status == 400:
        try:
            err = cast(dict[str, Any], response.json()).get("error", {})
            if isinstance(err, dict) and _is_content_filter_error(err):
                raise LLMContentFiltered(f"[{adapter_id}] content filtered by provider")
        except LLMContentFiltered:
            raise
        except Exception:
            pass
        raise LLMInvalidRequest(f"[{adapter_id}] bad request: HTTP 400")
    if status >= 500:
        raise LLMUnavailable(f"[{adapter_id}] service error: HTTP {status}")
    if status >= 400:
        raise LLMUnavailable(f"[{adapter_id}] unexpected client error: HTTP {status}")
