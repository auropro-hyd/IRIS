"""OTEL span and structured-log instrumentation shared by all LLM adapters."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from iris_engine.contracts.llm_provider import (
    LLMError,
    LLMRequest,
    LLMResponse,
    TenantContext,
)

SPAN_NAME = "llm.complete"
_log = logging.getLogger("iris.llm")


@asynccontextmanager
async def instrument_complete(
    adapter_id: str,
    ctx: TenantContext,
    request: LLMRequest,
) -> AsyncGenerator[trace.Span]:
    """Async CM that wraps an adapter's complete() with an OTEL span.

    Sets initial span attributes, catches and records typed LLM errors, and
    sets StatusCode.OK on clean exit. The adapter is responsible for setting
    result attributes (llm.model, llm.input_tokens, llm.output_tokens,
    llm.latency_ms, llm.structured_output_used) before returning.
    """
    tracer = trace.get_tracer("iris.llm", "1.0.0")
    with tracer.start_as_current_span(SPAN_NAME) as span:
        span.set_attribute("llm.adapter_id", adapter_id)
        span.set_attribute("llm.tenant_id", ctx.tenant_id)
        span.set_attribute("llm.product_slug", ctx.product_slug)
        span.set_attribute("llm.structured_output_requested", request.schema is not None)
        try:
            yield span
        except LLMError as exc:
            span.set_attribute("llm.success", False)
            span.set_attribute("llm.error_category", type(exc).__name__)
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            _log.warning(
                "llm.complete failed",
                extra={
                    "adapter_id": adapter_id,
                    "tenant_id": ctx.tenant_id,
                    "product_slug": ctx.product_slug,
                    "error_category": type(exc).__name__,
                },
            )
            raise
        except Exception as exc:
            span.set_attribute("llm.success", False)
            span.set_attribute("llm.error_category", "UnexpectedError")
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            raise
        else:
            span.set_status(StatusCode.OK)


def log_complete_success(
    adapter_id: str,
    ctx: TenantContext,
    result: LLMResponse,
) -> None:
    """Emit a structured success log line after a successful complete()."""
    _log.info(
        "llm.complete succeeded",
        extra={
            "adapter_id": adapter_id,
            "tenant_id": ctx.tenant_id,
            "product_slug": ctx.product_slug,
            "model": result.model,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "latency_ms": result.latency_ms,
        },
    )
