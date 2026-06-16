"""OTEL span + structured log instrumentation shared by all OCR adapters."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from iris_engine.contracts.ocr_engine import OCRError, OCRResult, TenantContext

SPAN_NAME = "ocr.extract"
_log = logging.getLogger("iris.ocr")


@asynccontextmanager
async def instrument_extract(
    adapter_id: str,
    ctx: TenantContext,
    document_id: UUID,
    content_type: str,
) -> AsyncGenerator[trace.Span]:
    """Async CM that wraps an adapter's extract() with an OTEL span.

    Sets initial span attributes, catches and records typed OCR errors, and
    sets StatusCode.OK on clean exit. The adapter is responsible for setting
    result attributes (ocr.total_pages, ocr.total_latency_ms, ocr.success)
    and calling log_extract_success() before returning.
    """
    tracer = trace.get_tracer("iris.ocr", "1.0.0")
    with tracer.start_as_current_span(SPAN_NAME) as span:
        span.set_attribute("ocr.adapter_id", adapter_id)
        span.set_attribute("ocr.tenant_id", ctx.tenant_id)
        span.set_attribute("ocr.product_slug", ctx.product_slug)
        span.set_attribute("ocr.document_id", str(document_id))
        span.set_attribute("ocr.content_type", content_type)
        try:
            yield span
        except OCRError as exc:
            span.set_attribute("ocr.success", False)
            span.set_attribute("ocr.error_category", type(exc).__name__)
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            _log.warning(
                "ocr.extract failed",
                extra={
                    "adapter_id": adapter_id,
                    "tenant_id": ctx.tenant_id,
                    "product_slug": ctx.product_slug,
                    "document_id": str(document_id),
                    "content_type": content_type,
                    "error_category": type(exc).__name__,
                },
            )
            raise
        except Exception as exc:
            span.set_attribute("ocr.success", False)
            span.set_attribute("ocr.error_category", "UnexpectedError")
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            raise
        else:
            span.set_status(StatusCode.OK)


def log_extract_success(
    adapter_id: str,
    ctx: TenantContext,
    result: OCRResult,
) -> None:
    """Emit structured success log line after a successful extract()."""
    _log.info(
        "ocr.extract succeeded",
        extra={
            "adapter_id": adapter_id,
            "tenant_id": ctx.tenant_id,
            "product_slug": ctx.product_slug,
            "total_pages": result.total_pages,
            "total_latency_ms": result.total_latency_ms,
        },
    )
