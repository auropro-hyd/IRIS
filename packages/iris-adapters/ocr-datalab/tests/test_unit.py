"""Unit tests for DatalabOCREngine - all HTTP calls are mocked.

Contract clause coverage:
  C-OCR-001  id / version
  C-OCR-002  fixture PDF extracts markdown
  C-OCR-003  multi-page ordering
  C-OCR-004  bounding box format (empty list - Datalab returns no bboxes)
  C-OCR-005  confidence in [0, 1]
  C-OCR-006  unsupported content type
  C-OCR-007  malformed document (API failure response)
  C-OCR-008  empty bytes
  C-OCR-009  adapter_id in result
  C-OCR-010  PNG input accepted
  HTTP error mapping: 400, 401, 403, 413, 429, 5xx, 529, timeout, connect error
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
from iris_ocr_datalab import DatalabOCREngine

_CTX = TenantContext(tenant_id="tenant-1", product_slug="commercial-auto/in")
_DOC_ID = uuid4()
_PDF_BYTES = b"%PDF-1.4 fixture"
_PNG_BYTES = b"\x89PNG\r\n\x1a\n fixture"
_CHECK_URL = "https://www.datalab.to/api/v1/convert/check/abc123"


def _run(coro):
    return asyncio.run(coro)


def _make_engine() -> tuple[DatalabOCREngine, AsyncMock]:
    client: AsyncMock = AsyncMock(spec=httpx.AsyncClient)
    engine = DatalabOCREngine(
        api_key="test-key",  # pragma: allowlist secret
        poll_interval=0.0,
        _http_client=client,
    )
    return engine, client


def _submit_ok(check_url: str = _CHECK_URL) -> httpx.Response:
    return httpx.Response(200, json={"request_check_url": check_url})


def _poll_complete(
    markdown: str = "IRIS Insurance Reference Intelligence Stack",
    page_count: int = 1,
    quality_score: float = 4.0,
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "status": "complete",
            "success": True,
            "markdown": markdown,
            "page_count": page_count,
            "parse_quality_score": quality_score,
        },
    )


def _poll_complete_no_quality(
    markdown: str = "IRIS Insurance Reference Intelligence Stack",
    page_count: int = 1,
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "status": "complete",
            "success": True,
            "markdown": markdown,
            "page_count": page_count,
        },
    )


# C-OCR-001 ----------------------------------------------------------------


def test_c001_id_is_datalab():
    engine, _ = _make_engine()
    assert engine.id == "datalab"


def test_c001_version_is_semver():
    engine, _ = _make_engine()
    parts = engine.version.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts)


# C-OCR-002 ----------------------------------------------------------------


def test_c002_pdf_extracts_markdown():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = _poll_complete("IRIS Insurance Reference Intelligence Stack")

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    assert "iris" in result.pages[0].markdown.lower()


# C-OCR-003 ----------------------------------------------------------------


def test_c003_multipage_ordering():
    engine, client = _make_engine()
    pages_md = "page 1\n\n---\n\npage 2\n\n---\n\npage 3"
    client.post.return_value = _submit_ok()
    client.get.return_value = _poll_complete(markdown=pages_md, page_count=3)

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    assert [pg.page_number for pg in result.pages] == [1, 2, 3]
    assert result.pages[0].markdown == "page 1"
    assert result.pages[2].markdown == "page 3"


# C-OCR-004 ----------------------------------------------------------------


def test_c004_bboxes_are_empty_list():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = _poll_complete()

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    for page in result.pages:
        assert list(page.bboxes) == []


# C-OCR-005 ----------------------------------------------------------------


def test_c005_confidence_in_range():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = _poll_complete(quality_score=3.5)

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    for page in result.pages:
        assert 0.0 <= page.confidence <= 1.0


def test_c005_quality_score_normalized():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = _poll_complete(quality_score=5.0)

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    assert result.pages[0].confidence == 1.0


def test_c005_missing_quality_score_defaults_to_0():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = _poll_complete_no_quality()

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    assert result.pages[0].confidence == 0.0


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


def test_c007_failed_status_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = httpx.Response(
        200,
        json={
            "status": "failed",
            "success": False,
            "error": "Could not parse document",
        },
    )

    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, b"not-a-pdf", "application/pdf"))


def test_c007_success_false_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = httpx.Response(
        200,
        json={
            "status": "complete",
            "success": False,
            "error": "Page concurrency limit reached",
        },
    )

    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


# C-OCR-008 ----------------------------------------------------------------


def test_c008_empty_bytes_raises_malformed():
    engine, _ = _make_engine()
    with pytest.raises(OCRMalformedDocument):
        _run(engine.extract(_CTX, _DOC_ID, b"", "application/pdf"))


# C-OCR-009 ----------------------------------------------------------------


def test_c009_adapter_id_in_result():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = _poll_complete()

    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))

    assert result.adapter_id == engine.id


# C-OCR-010 ----------------------------------------------------------------


def test_c010_png_input_accepted():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = _poll_complete(page_count=1)

    result = _run(engine.extract(_CTX, _DOC_ID, _PNG_BYTES, "image/png"))

    assert result.total_pages == 1


# HTTP error mapping -------------------------------------------------------


def test_http_400_raises_malformed():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(400)
    with pytest.raises(OCRMalformedDocument):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


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


def test_http_413_raises_document_too_large():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(413)
    with pytest.raises(OCRDocumentTooLarge):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_http_429_raises_rate_limited():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(429)
    with pytest.raises(OCRRateLimited):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_http_500_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(500)
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_http_529_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(529)
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


def test_missing_check_url_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(200, json={"request_check_url": ""})
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_non_json_submit_response_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(200, text="<html>Gateway Timeout</html>")
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_non_json_poll_response_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = httpx.Response(200, text="<html>error</html>")
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_poll_timeout_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.side_effect = httpx.TimeoutException("poll timed out")
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_poll_deadline_exceeded_raises_unavailable() -> None:
    client: AsyncMock = AsyncMock(spec=httpx.AsyncClient)
    engine = DatalabOCREngine(
        api_key="test-key",  # pragma: allowlist secret
        poll_interval=0.0,
        max_poll_seconds=0.0,
        _http_client=client,
    )
    client.post.return_value = _submit_ok()
    client.get.return_value = httpx.Response(200, json={"status": "pending"})
    with pytest.raises(OCRUnavailable, match="did not complete within"):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_http_4xx_catch_all_raises_unavailable():
    engine, client = _make_engine()
    client.post.return_value = httpx.Response(402)
    with pytest.raises(OCRUnavailable):
        _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))


def test_page_count_fewer_than_split_trims_pages():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = _poll_complete(
        markdown="page one\n\n---\n\npage two\n\n---\n\npage three",
        page_count=2,
    )
    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))
    assert result.total_pages == 2


def test_page_count_more_than_split_pads_pages():
    engine, client = _make_engine()
    client.post.return_value = _submit_ok()
    client.get.return_value = _poll_complete(markdown="only one page", page_count=3)
    result = _run(engine.extract(_CTX, _DOC_ID, _PDF_BYTES, "application/pdf"))
    assert result.total_pages == 3
