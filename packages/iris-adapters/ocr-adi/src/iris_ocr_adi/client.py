"""Azure Document Intelligence OCR adapter.

Authentication: API key via Ocp-Apim-Subscription-Key header.
Transport: raw httpx.AsyncClient - no Azure SDK dependency.
Model: prebuilt-layout (pages, lines, words, bounding boxes).

ADI analysis is asynchronous: POST starts the job (202 + Operation-Location),
GET polls until status == "succeeded" or "failed".
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

import httpx
from iris_engine.contracts.ocr_engine import (
    VALID_CONTENT_TYPES,
    BBox,
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

_ADI_API_VERSION = "2024-11-30"
_ADI_INVALID_CONTENT_CODES = frozenset({"InvalidContent"})
_ADI_TOO_LARGE_CODES = frozenset({"ContentTooLarge"})


class AdiOCREngine:
    id: str = "adi"
    version: str = "1.0.0"

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str = "prebuilt-layout",
        *,
        poll_interval: float = 1.0,
        _http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._poll_interval = poll_interval
        self._http_client = _http_client

    async def extract(
        self,
        ctx: TenantContext,
        document_id: UUID,
        content: bytes,
        content_type: str,
    ) -> OCRResult:
        if content_type not in VALID_CONTENT_TYPES:
            raise OCRUnsupportedContentType(
                f"ADI adapter does not support content type {content_type!r}"
            )
        if not content:
            raise OCRMalformedDocument("content is empty")

        if self._http_client is not None:
            return await self._do_extract(self._http_client, document_id, content, content_type)
        async with httpx.AsyncClient(timeout=60.0) as client:
            return await self._do_extract(client, document_id, content, content_type)

    async def _do_extract(
        self,
        client: httpx.AsyncClient,
        document_id: UUID,
        content: bytes,
        content_type: str,
    ) -> OCRResult:
        start = time.monotonic()
        url = f"{self._endpoint}/documentintelligence/documentModels/{self._model}:analyze"
        try:
            response = await client.post(
                url,
                content=content,
                headers={
                    "Ocp-Apim-Subscription-Key": self._api_key,
                    "Content-Type": content_type,
                },
                params={"api-version": _ADI_API_VERSION},
            )
        except httpx.TimeoutException as exc:
            raise OCRUnavailable("ADI request timed out") from exc
        except httpx.ConnectError as exc:
            raise OCRUnavailable("ADI connection failed") from exc

        _raise_for_status(response)
        operation_url = response.headers.get("Operation-Location")
        if not operation_url:
            raise OCRUnavailable("ADI response missing Operation-Location header")
        body = await self._poll(client, operation_url)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return _map_result(document_id, self.id, body, elapsed_ms)

    async def _poll(self, client: httpx.AsyncClient, operation_url: str) -> dict[str, Any]:
        while True:
            try:
                response = await client.get(
                    operation_url,
                    headers={"Ocp-Apim-Subscription-Key": self._api_key},
                )
            except httpx.TimeoutException as exc:
                raise OCRUnavailable("ADI poll timed out") from exc

            _raise_for_status(response)
            try:
                body: dict[str, Any] = response.json()
            except Exception as exc:
                raise OCRUnavailable("ADI returned a non-JSON poll response") from exc
            status: str = body.get("status", "")

            if status == "succeeded":
                return body
            if status == "failed":
                error: dict[str, str] = body.get("error", {})
                code = error.get("code", "")
                msg = error.get("message", code or "unknown error")
                if code in _ADI_INVALID_CONTENT_CODES:
                    raise OCRMalformedDocument(f"ADI rejected document: {msg}")
                if code in _ADI_TOO_LARGE_CODES:
                    raise OCRDocumentTooLarge(f"ADI document too large: {msg}")
                raise OCRUnavailable(f"ADI analysis failed: {msg}")

            await asyncio.sleep(self._poll_interval)


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status in {401, 403}:
        raise OCRAuthenticationFailed(f"ADI authentication failed: HTTP {status}")
    if status == 429:
        raise OCRRateLimited("ADI rate limit exceeded")
    if status >= 500:
        raise OCRUnavailable(f"ADI service error: HTTP {status}")
    if status >= 400:
        raise OCRUnavailable(f"ADI unexpected client error: HTTP {status}")


def _polygon_to_bbox(polygon: list[float], unit: str) -> BBox:
    xs = polygon[0::2]
    ys = polygon[1::2]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    # ADI uses "inch" for PDFs/TIFFs and "pixel" for PNG/JPEG.
    # 96 DPI is the standard screen approximation for inch->pixel conversion.
    scale = 96.0 if unit == "inch" else 1.0
    return BBox(
        x=int(min_x * scale),
        y=int(min_y * scale),
        width=max(1, int((max_x - min_x) * scale)),
        height=max(1, int((max_y - min_y) * scale)),
    )


def _map_result(
    document_id: UUID,
    adapter_id: str,
    body: dict[str, Any],
    total_latency_ms: int,
) -> OCRResult:
    analyze_result: dict[str, Any] = body.get("analyzeResult", {})
    raw_pages: list[dict[str, Any]] = analyze_result.get("pages", [])
    ocr_pages = []
    for page in raw_pages:
        page_number: int = page["pageNumber"]
        unit: str = page.get("unit", "inch")
        lines: list[dict[str, Any]] = page.get("lines", [])
        words: list[dict[str, Any]] = page.get("words", [])
        markdown = "\n".join(line["content"] for line in lines)
        bboxes = [_polygon_to_bbox(w["polygon"], unit) for w in words if "polygon" in w]
        confidences = [float(w["confidence"]) for w in words if "confidence" in w]
        raw_confidence = sum(confidences) / len(confidences) if confidences else 1.0
        ocr_pages.append(
            OCRPageResult(
                page_number=page_number,
                markdown=markdown,
                bboxes=bboxes,
                confidence=min(1.0, max(0.0, raw_confidence)),
            )
        )
    return OCRResult(
        document_id=document_id,
        adapter_id=adapter_id,
        pages=ocr_pages,
        total_pages=len(ocr_pages),
        total_latency_ms=total_latency_ms,
    )
