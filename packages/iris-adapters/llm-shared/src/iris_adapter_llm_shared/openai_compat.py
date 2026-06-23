"""OpenAI-compatible HTTP base class for LLM adapters.

Handles the shared HTTP shape used by Azure OpenAI, OpenAI direct, and the
local vLLM/Ollama adapter. Subclasses override _base_url() and _auth_headers()
only; all HTTP, error mapping, structured output (JSON-mode), and retry logic
is provided here.

Anthropic uses a different API shape and does not inherit from this class.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, cast

import httpx
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

from iris_adapter_llm_shared.retry import RetryConfig, with_retry


class OpenAICompatProvider(ABC):
    """Base class for OpenAI-compatible LLM adapters.

    Subclasses must implement _base_url() and _auth_headers(). They may also
    override _model_for_hint() to map model_hint values to model identifiers.
    """

    version: str = "1.0.0"

    def __init__(
        self,
        *,
        retry_config: RetryConfig | None = None,
        _http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._retry_config = retry_config or RetryConfig()
        self._http_client = _http_client

    @property
    @abstractmethod
    def id(self) -> str:
        """Adapter identifier. One of: azure-openai, openai, local."""

    @abstractmethod
    def _base_url(self) -> str:
        """Chat completions endpoint URL."""

    @abstractmethod
    def _auth_headers(self) -> dict[str, str]:
        """Authorization headers for the provider."""

    def _model_for_hint(self, hint: str | None, default: str) -> str:
        """Map a model_hint to a model identifier. Override per adapter."""
        return default

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
        model = self._model_for_hint(request.model_hint, "gpt-4o-mini")
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
                self._base_url(),
                json=body,
                headers={"Content-Type": "application/json", **self._auth_headers()},
            )
        except httpx.TimeoutException as exc:
            raise LLMUnavailable(f"[{self.id}] request timed out") from exc
        except httpx.ConnectError as exc:
            raise LLMUnavailable(f"[{self.id}] connection failed") from exc
        _raise_for_status(response, self.id)
        return response


# ── helpers ───────────────────────────────────────────────────────────────────


def _build_request_body(model: str, request: LLMRequest) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    messages.append({"role": "user", "content": request.prompt})

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": request.temperature,
    }
    if request.max_output_tokens is not None:
        body["max_tokens"] = request.max_output_tokens
    if request.stop:
        body["stop"] = request.stop
    if request.schema is not None:
        body["response_format"] = {"type": "json_object"}
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
        choice = data["choices"][0]
        text: str = choice["message"]["content"] or ""
        usage_data: dict[str, int] = data.get("usage", {})
        input_tokens = int(usage_data.get("prompt_tokens", 0))
        output_tokens = int(usage_data.get("completion_tokens", 0))
        finish_reason: str = choice.get("finish_reason", "")
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMUnavailable(f"[{adapter_id}] unexpected response shape: {exc}") from exc

    if finish_reason == "content_filter":
        raise LLMContentFiltered(f"[{adapter_id}] response blocked by content filter")
    if finish_reason == "length":
        raise LLMContextWindowExceeded(
            f"[{adapter_id}] response truncated: context window exceeded"
        )

    structured: BaseModel | None = None
    if schema is not None:
        try:
            structured = schema.model_validate_json(text)
        except (ValidationError, ValueError) as exc:
            raise LLMSchemaViolation(
                f"[{adapter_id}] structured output did not match {schema.__name__}: {exc}"
            ) from exc

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


def _raise_for_status(response: httpx.Response, adapter_id: str) -> None:
    status = response.status_code
    if status in {401, 403}:
        raise LLMAuthenticationFailed(f"[{adapter_id}] authentication failed: HTTP {status}")
    if status == 429:
        raise LLMRateLimited(f"[{adapter_id}] rate limit exceeded")
    if status == 400:
        raise LLMInvalidRequest(f"[{adapter_id}] bad request: HTTP 400")
    if status >= 500:
        raise LLMUnavailable(f"[{adapter_id}] service error: HTTP {status}")
    if status >= 400:
        raise LLMUnavailable(f"[{adapter_id}] unexpected client error: HTTP {status}")
