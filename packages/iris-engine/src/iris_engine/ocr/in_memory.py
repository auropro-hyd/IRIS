"""InMemoryOCREngine: fake OCR engine for tests and local development.

Returns canned OCRResult values when pre-registered, or a minimal default
result otherwise. Raises the correct typed errors for invalid inputs so it
satisfies the OCREngine contract without contacting any real service.
"""

from __future__ import annotations

from uuid import UUID

from iris_engine.contracts.ocr_engine import (
    VALID_CONTENT_TYPES,
    OCRMalformedDocument,
    OCRPageResult,
    OCRResult,
    OCRUnsupportedContentType,
    TenantContext,
)


class InMemoryOCREngine:
    """Fake OCR engine that returns pre-set or default OCRResult values."""

    version: str = "1.0.0"

    def __init__(
        self,
        responses: dict[UUID, OCRResult] | None = None,
        adapter_id: str = "in-memory",
    ) -> None:
        self.id = adapter_id
        self._responses: dict[UUID, OCRResult] = responses or {}

    async def extract(
        self,
        ctx: TenantContext,
        document_id: UUID,
        content: bytes,
        content_type: str,
    ) -> OCRResult:
        from iris_engine.ocr.tracing import instrument_extract, log_extract_success

        async with instrument_extract(self.id, ctx, document_id, content_type) as span:
            if content_type not in VALID_CONTENT_TYPES:
                raise OCRUnsupportedContentType(f"content type {content_type!r} is not supported")
            if not content:
                raise OCRMalformedDocument("content is empty")
            if document_id in self._responses:
                result = self._responses[document_id]
            else:
                page = OCRPageResult(
                    page_number=1,
                    markdown="",
                    bboxes=[],
                    confidence=1.0,
                )
                result = OCRResult(
                    document_id=document_id,
                    adapter_id=self.id,
                    pages=[page],
                    total_pages=1,
                    total_latency_ms=0,
                )
            span.set_attribute("ocr.total_pages", result.total_pages)
            span.set_attribute("ocr.total_latency_ms", result.total_latency_ms)
            span.set_attribute("ocr.success", True)
            log_extract_success(self.id, ctx, result)
            return result
