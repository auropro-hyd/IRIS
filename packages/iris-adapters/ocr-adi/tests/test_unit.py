"""Unit tests for AdiOCREngine - all ADI HTTP calls are mocked.

Contract clause coverage:
  C-OCR-001  id / version
  C-OCR-002  fixture PDF extracts markdown
  C-OCR-003  multi-page ordering
  C-OCR-004  bounding box format
  C-OCR-005  confidence in [0, 1]
  C-OCR-006  unsupported content type
  C-OCR-007  malformed PDF (ADI failure response)
  C-OCR-008  empty bytes
  C-OCR-009  adapter_id in result
  C-OCR-010  PNG input accepted
  HTTP error mapping: 401, 403, 429, 5xx, timeout, connect error
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from iris_engine.contracts.ocr_engine import (
    OCRAuthenticationFailed,
    OCRDocumentTooLarge,
    OCRMalformedDocument,
    OCRRateLimited,
    OCRUnavailable,
    OCRUnsupportedContentType,
    TenantContext,
)
from iris_ocr_adi import AdiOCREngine

_CTX = TenantContext(tenant_id="tenant-1", product_slug="commercial-auto/in")
_DOC_ID = uuid4()
_PDF_BYTES = b"%PDF-1.4 fixture"
_PNG_BYTES = b"\x89PNG\r\n\x1a\n fixture"
_OPERATION_URL = "https://test.cognitiveservices.azure.com/operation/abc123"


def _run(coro):
    return asyncio.run(coro)


def _make_engine() -> tuple[AdiOCREngine, AsyncMock]:
    client: AsyncMock = AsyncMock(spec=httpx.AsyncClient)
    engine = AdiOCREngine(
        endpoint="https://test.cognitiveservices.azure.com",
        api_key="test-key",  # pragma: allowlist secret
        poll_interval=0.0,
        _http_client=client,
    )
    return engine, client


def _post_202() -> httpx.Response:
    return httpx.Response(202, headers={"Operation-Location": _OPERATION_URL})


def _poll_ok(pages: list[dict]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"status": "succeeded", "analyzeResult": {"pages": pages}},
    )


def _single_page(text: str = "IRIS Insurance Reference Intelligence Stack") -> list[dict]:
    return [
        {
            "pageNumber": 1,
            "unit": "inch",
            "lines": [{"content": text}],
            "words": [
                {
                    "content": text,
                    "confidence": 0.95,
                    "polygon": [0.5, 0.5, 2.0, 0.5, 2.0, 0.7, 0.5, 0.7],
                }
            ],
        }
    ]


# C-OCR-001 ----------------------------------------------------------------


def test_c001_id_is_adi():
    engine, _ = _make_engine()
    assert engine.id == "adi"


def test_c001_version_is_semver():
    engine, _ = _make_engine()
    parts = engine.version.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts)


# C-OCR-002 ----------------------------------------------------------------


def test_c002_pdf_extracts_markdown():
    engine, client = _make_engine()
    client.post.return_value = _post_202()
    client.get.return_value = _poll_ok(_single_page("IRIS Insurance Reference Intelligence Stack"))

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    assert "iris" in result.pages[0].markdown.lower()


# C-OCR-003 ----------------------------------------------------------------


def test_c003_multipage_ordering():
    engine, client = _make_engine()
    pages = [
        {
            "pageNumber": p,
            "unit": "inch",
            "lines": [{"content": f"page {p}"}],
            "words": [],
        }
        for p in [1, 2, 3]
    ]
    client.post.return_value = _post_202()
    client.get.return_value = _poll_ok(pages)

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    assert [pg.page_number for pg in result.pages] == [1, 2, 3]


# C-OCR-004 ----------------------------------------------------------------


def test_c004_bbox_non_negative_xy_positive_wh():
    engine, client = _make_engine()
    client.post.return_value = _post_202()
    client.get.return_value = _poll_ok(_single_page())

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    for page in result.pages:
        for bbox in page.bboxes:
            assert bbox.x >= 0
            assert bbox.y >= 0
            assert bbox.width > 0
            assert bbox.height > 0


# C-OCR-005 ----------------------------------------------------------------


def test_c005_confidence_in_range():
    engine, client = _make_engine()
    client.post.return_value = _post_202()
    client.get.return_value = _poll_ok(_single_page())

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    for page in result.pages:
        assert 0.0 <= page.confidence <= 1.0


# C-OCR-006 ----------------------------------------------------------------


def test_c006_unsupported_content_type_raises():
    engine, _ = _make_engine()
    with pytest.raises(OCRUnsupportedContentType):
        _run(engine.extract(_CTX, _DOC_ID, b"data", "application/json"))


def test_c006_error_does_not_contain_bytes():
    engine, _ = _make_engine()
    payload = b"sensitive document bytes"
    try:
        _run(engine.extract(_CTX, _DOC_ID, payload, "text/plain"))
    except OCRUnsupportedContentType as exc:
        assert b"sensitive" not in str(exc).encode()


# C-OCR-007 ----------------------------------------------------------------


def test_c007_adi_invalid_content_raises_malformed():
    engine, client = _make_engine()
    client.post.return_value = _post_202()
    client.get.return_value = httpx.Response(
        200,
        json={
            "status": "failed",
            "error": {
                "code": "InvalidContent",
                "message": "Content is not a valid PDF",
            },
        },
    )

    with pytest.raises(OCRMalformedDocument):
        _run(engine.extract(_CTX, _DOC_ID, b"not-a-pdf", "application/pdf"))


# C-OCR-008 ----------------------------------------------------------------


def test_c008_empty_bytes_raises_malformed():
    engine, _ = _make_engine()
    with pytest.raises(OCRMalformedDocument):
        _run(engine.extract(_CTX, _DOC_ID, b"", "application/pdf"))


# C-OCR-009 ----------------------------------------------------------------


def test_c009_adapter_id_in_result():
    engine, client = _make_engine()
    client.post.return_value = _post_202()
    client.get.return_value = _poll_ok(_single_page())

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    assert result.adapter_id == engine.id


# C-OCR-010 ----------------------------------------------------------------


def test_c010_png_input_accepted():
    engine, client = _make_engine()
    client.post.return_value = _post_202()
    client.get.return_value = _poll_ok(_single_page())

    result = _run(engine.extract(_CTX, _DOC_ID, _PNG_BYTES, "image/png"))

    assert result.total_pages == 1


# HTTP error mapping -------------------------------------------------------


def test_http_401_raises_auth_failed():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(401)
    with pytest.raises(OCRAuthenticationFailed):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_http_403_raises_auth_failed():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(403)
    with pytest.raises(OCRAuthenticationFailed):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_http_429_raises_rate_limited():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(429)
    with pytest.raises(OCRRateLimited):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_http_503_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(503)
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_connect_error_raises_unavailable():
    engine, client = _make_engine()
    client.post.side_effect = httpx.ConnectError("connection refused")
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_timeout_raises_unavailable():
    engine, client = _make_engine()
    client.post.side_effect = httpx.TimeoutException("timed out")
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_adi_failed_status_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = _post_202()
    client.get.return_value = httpx.Response(
        200,
        json={
            "status": "failed",
            "error": {"code": "InternalServerError", "message": "ADI internal error"},
        },
    )
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_content_too_large_raises_document_too_large():
    engine, client = _make_engine()
    client.post.return_value = _post_202()
    client.get.return_value = httpx.Response(
        200,
        json={
            "status": "failed",
            "error": {"code": "ContentTooLarge", "message": "Document exceeds limit"},
        },
    )
    with pytest.raises(OCRDocumentTooLarge):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_missing_operation_location_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(202)  # no Operation-Location header
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_non_json_poll_response_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = _post_202()
    client.get.return_value = httpx.Response(200, text="<html>Gateway Timeout</html>")
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))
