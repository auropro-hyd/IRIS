"""Datalab document conversion OCR adapter.

Authentication: API key via X-API-Key header.
Transport: raw httpx.AsyncClient - no datalab_sdk dependency.

Datalab conversion is asynchronous: POST starts the job (returns
request_check_url), GET polls until status == "complete" or "failed".

Bounding boxes: Datalab's convert endpoint returns markdown only, no
per-word coordinates. bboxes is always empty for this adapter.

Confidence: Datalab returns parse_quality_score on a 0-5 scale, normalised
to [0.0, 1.0] and applied uniformly to every page.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

import httpx
from iris_engine.contracts.ocr_engine import (
    VALID_CONTENT_TYPES,
    OCRAuthenticationFailed,
    OCRDocumentTooLarge,
    OCRMalformedDocument,
    OCRPageResult,
    OCRRateLimited,
    OCRResult,
    OCRUnavailable,
    OCRUnsupportedContentType,
    TenantContext,
)

_DATALAB_CONVERT_URL = "https://www.datalab.to/api/v1/convert"
_DATALAB_MAX_QUALITY_SCORE = 5.0

# Datalab's paginated markdown uses a horizontal rule as a page separator.
# The marker library (which powers Datalab) emits this delimiter between pages.
_PAGE_SEPARATORS = ["\n\n---\n\n", "\n---\n", "\f"]

# MIME type -> file extension for multipart upload filename hint.
_MIME_TO_EXT: dict[str, str] = {
    "application/pdf": "document.pdf",
    "image/png": "document.png",
    "image/jpeg": "document.jpg",
    "image/tiff": "document.tiff",
}


class DatalabOCREngine:
    id: str = "datalab"
    version: str = "1.0.0"

    def __init__(
        self,
        api_key: str,
        mode: str = "balanced",
        *,
        poll_interval: float = 2.0,
        max_poll_seconds: float = 300.0,
        _http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._mode = mode
        self._poll_interval = poll_interval
        self._max_poll_seconds = max_poll_seconds
        self._http_client = _http_client

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
                raise OCRUnsupportedContentType(
                    f"Datalab adapter does not support content type {content_type!r}"
                )
            if not content:
                raise OCRMalformedDocument("content is empty")

            if self._http_client is not None:
                result = await self._do_extract(
                    self._http_client, document_id, content, content_type
                )
            else:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    result = await self._do_extract(client, document_id, content, content_type)

            span.set_attribute("ocr.total_pages", result.total_pages)
            span.set_attribute("ocr.total_latency_ms", result.total_latency_ms)
            span.set_attribute("ocr.success", True)
            log_extract_success(self.id, ctx, result)
            return result

    async def _do_extract(
        self,
        client: httpx.AsyncClient,
        document_id: UUID,
        content: bytes,
        content_type: str,
    ) -> OCRResult:
        start = time.monotonic()
        filename = _MIME_TO_EXT.get(content_type, "document.bin")

        try:
            response = await client.post(
                _DATALAB_CONVERT_URL,
                headers={"X-API-Key": self._api_key},
                files={"file": (filename, content, content_type)},
                data={
                    "output_format": "markdown",
                    "mode": self._mode,
                    "paginate": "true",
                },
            )
        except httpx.TimeoutException as exc:
            raise OCRUnavailable("Datalab request timed out") from exc
        except httpx.ConnectError as exc:
            raise OCRUnavailable("Datalab connection failed") from exc

        _raise_for_status(response)

        try:
            body: dict[str, Any] = response.json()
        except Exception as exc:
            raise OCRUnavailable("Datalab returned a non-JSON response") from exc

        check_url: str = body.get("request_check_url", "")
        if not check_url:
            raise OCRUnavailable("Datalab response missing request_check_url")

        result = await self._poll(client, check_url)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return _map_result(document_id, self.id, result, elapsed_ms)

    async def _poll(self, client: httpx.AsyncClient, check_url: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._max_poll_seconds
        while True:
            if time.monotonic() > deadline:
                raise OCRUnavailable(
                    f"Datalab conversion did not complete within {self._max_poll_seconds:.0f}s"
                )
            await asyncio.sleep(self._poll_interval)

            try:
                response = await client.get(
                    check_url,
                    headers={"X-API-Key": self._api_key},
                )
            except httpx.TimeoutException as exc:
                raise OCRUnavailable("Datalab poll timed out") from exc

            _raise_for_status(response)

            try:
                body: dict[str, Any] = response.json()
            except Exception as exc:
                raise OCRUnavailable("Datalab returned a non-JSON poll response") from exc

            status: str = body.get("status", "")

            if status == "complete":
                if not body.get("success", True):
                    error_msg = body.get("error", "unknown error")
                    raise OCRUnavailable(f"Datalab conversion failed: {error_msg}")
                return body

            if status == "failed":
                error_msg = body.get("error", "unknown error")
                raise OCRUnavailable(f"Datalab conversion failed: {error_msg}")


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status in {401, 403}:
        raise OCRAuthenticationFailed(f"Datalab authentication failed: HTTP {status}")
    if status == 413:
        raise OCRDocumentTooLarge("Datalab document too large")
    if status == 429:
        raise OCRRateLimited("Datalab rate limit exceeded")
    if status in {500, 529} or status >= 500:
        raise OCRUnavailable(f"Datalab service error: HTTP {status}")
    if status == 400:
        raise OCRMalformedDocument(f"Datalab rejected document: HTTP {status}")
    if status >= 400:
        raise OCRUnavailable(f"Datalab unexpected client error: HTTP {status}")


def _split_pages(markdown: str) -> list[str]:
    """Split paginated markdown into per-page strings.

    Datalab inserts a page delimiter between pages when paginate=true.
    Falls back to treating the whole document as one page if no separator found.
    """
    for sep in _PAGE_SEPARATORS:
        if sep in markdown:
            return [p.strip() for p in markdown.split(sep)]
    return [markdown.strip()]


def _map_result(
    document_id: UUID,
    adapter_id: str,
    body: dict[str, Any],
    total_latency_ms: int,
) -> OCRResult:
    markdown: str = body.get("markdown") or ""
    page_count: int = body.get("page_count") or 1
    quality = body.get("parse_quality_score")
    confidence = (
        min(1.0, max(0.0, float(quality) / _DATALAB_MAX_QUALITY_SCORE))
        if quality is not None
        else 0.0
    )

    pages = _split_pages(markdown)

    # Align split result with reported page_count: pad or trim as needed.
    if len(pages) < page_count:
        pages += [""] * (page_count - len(pages))
    elif len(pages) > page_count:
        pages = pages[:page_count]

    ocr_pages = [
        OCRPageResult(
            page_number=i + 1,
            markdown=page_md,
            bboxes=[],
            confidence=confidence,
        )
        for i, page_md in enumerate(pages)
    ]

    return OCRResult(
        document_id=document_id,
        adapter_id=adapter_id,
        pages=ocr_pages,
        total_pages=len(ocr_pages),
        total_latency_ms=total_latency_ms,
    )
