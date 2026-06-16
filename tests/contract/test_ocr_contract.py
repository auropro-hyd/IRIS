"""Parametrised OCR contract suite.

Clauses C-OCR-001 through C-OCR-010 and C-OCR-LOCAL-001 are verified against
all five adapters: in-memory, adi, datalab, paddleocr, local.

HTTP adapters (ADI, Datalab) use injected mock httpx.AsyncClient instances.
Inference adapters (PaddleOCR, Tesseract) use injected mock pipeline/module.
InMemoryOCREngine uses pre-registered canned responses keyed on _DOC_ID.

C-OCR-007 (malformed PDF) is excluded from in-memory: InMemoryOCREngine does not
parse document bytes by design - it returns pre-registered results regardless of
content.

C-OCR-011 (OTEL span attributes) is deferred to T038.
"""

from __future__ import annotations

import asyncio
import io
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import httpx
import pymupdf
import pytest
from iris_engine.contracts.ocr_engine import (
    VALID_ADAPTER_IDS,
    BBox,
    OCRMalformedDocument,
    OCRPageResult,
    OCRResult,
    OCRUnsupportedContentType,
    TenantContext,
)
from iris_engine.ocr.in_memory import InMemoryOCREngine
from PIL import Image

pytestmark = pytest.mark.contract

_IRIS_TEXT = "IRIS Insurance Reference Intelligence Stack"
_CTX = TenantContext(tenant_id="tenant-test", product_slug="commercial-auto/in")
_DOC_ID = UUID("12345678-1234-5678-1234-567812345678")

# Adapters that run a real parser and must raise OCRMalformedDocument for corrupt input.
_CONTENT_VALIDATING = ["adi", "datalab", "paddleocr", "local"]
# Adapters that never make outbound network calls.
_LOCAL = ["local", "paddleocr"]
_ALL = ["in_memory"] + _CONTENT_VALIDATING

# Expected adapter.id per factory key.
_EXPECTED_IDS = {
    "adi": "adi",
    "datalab": "datalab",
    "paddleocr": "paddleocr",
    "local": "local",
    "in_memory": "in-memory",
}


# ── document fixtures ────────────────────────────────────────────────────────


def _make_pdf(num_pages: int = 1, text: str = _IRIS_TEXT) -> bytes:
    doc = pymupdf.open()
    for _ in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), text)
    return doc.tobytes()


def _make_png() -> bytes:
    img = Image.new("RGB", (200, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── per-adapter engine builders ──────────────────────────────────────────────


def _adi_engine(*, pages: int = 1, text: str = _IRIS_TEXT) -> Any:
    from iris_ocr_adi import AdiOCREngine

    words_list = [
        {
            "content": w,
            "confidence": 0.95,
            "polygon": [0.1, i * 0.5, 1.1, i * 0.5, 1.1, i * 0.5 + 0.3, 0.1, i * 0.5 + 0.3],
        }
        for i, w in enumerate(text.split())
    ]
    adi_pages = [
        {
            "pageNumber": p + 1,
            "width": 8.5,
            "height": 11.0,
            "unit": "inch",
            "words": words_list,
            "lines": [{"content": text}],
        }
        for p in range(pages)
    ]

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    post_resp = MagicMock(spec=httpx.Response)
    post_resp.status_code = 202
    post_resp.headers = {"Operation-Location": "https://mock/operations/1"}
    mock_client.post.return_value = post_resp

    poll_resp = MagicMock(spec=httpx.Response)
    poll_resp.status_code = 200
    poll_resp.json.return_value = {
        "status": "succeeded",
        "analyzeResult": {"pages": adi_pages},
    }
    mock_client.get.return_value = poll_resp

    return AdiOCREngine(
        endpoint="https://mock.cognitiveservices.azure.com",
        api_key="test-key",  # pragma: allowlist secret
        poll_interval=0.0,
        _http_client=mock_client,
    )


def _datalab_engine(*, pages: int = 1, text: str = _IRIS_TEXT) -> Any:
    from iris_ocr_datalab import DatalabOCREngine

    if pages == 1:
        markdown = text
    else:
        parts = [text] + [f"page{i + 1}" for i in range(1, pages)]
        markdown = "\n\n---\n\n".join(parts)

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    submit_resp = MagicMock(spec=httpx.Response)
    submit_resp.status_code = 200
    submit_resp.json.return_value = {"request_check_url": "https://mock/check/1"}
    mock_client.post.return_value = submit_resp

    poll_resp = MagicMock(spec=httpx.Response)
    poll_resp.status_code = 200
    poll_resp.json.return_value = {
        "status": "complete",
        "success": True,
        "markdown": markdown,
        "page_count": pages,
        "parse_quality_score": 4.5,
    }
    mock_client.get.return_value = poll_resp

    return DatalabOCREngine(
        api_key="test-key",  # pragma: allowlist secret
        poll_interval=0.0,
        _http_client=mock_client,
    )


def _paddleocr_engine(*, pages: int = 1, text: str = _IRIS_TEXT) -> Any:
    from iris_ocr_paddleocr import PaddleOCREngine

    class _MockBlock:
        def __init__(self, content: str, bbox: list[int]) -> None:
            self.content = content
            self.bbox = bbox

    class _MockResult:
        def __init__(self, content: str) -> None:
            self._content = content

        def __getitem__(self, key: str) -> Any:
            if key == "parsing_res_list":
                return [_MockBlock(self._content, [10, 10, 200, 40])]
            raise KeyError(key)

    mock_pipeline = MagicMock()
    if pages == 1:
        mock_pipeline.predict.return_value = [_MockResult(text)]
    else:
        side = [[_MockResult(text if i == 0 else f"page{i + 1}")] for i in range(pages)]
        mock_pipeline.predict.side_effect = side

    return PaddleOCREngine(_pipeline=mock_pipeline)


def _local_engine(*, pages: int = 1, text: str = _IRIS_TEXT) -> Any:
    from iris_ocr_local import TesseractEngine

    def _page_data(content: str) -> dict[str, list[Any]]:
        ws = content.split()
        n = len(ws)
        return {
            "text": ws,
            "conf": [90] * n,
            "block_num": [1] * n,
            "left": [10] * n,
            "top": [10] * n,
            "width": [80] * n,
            "height": [20] * n,
        }

    mock_pt = MagicMock()
    mock_pt.Output.DICT = "dict"
    if pages == 1:
        mock_pt.image_to_data.return_value = _page_data(text)
    else:
        side = [_page_data(text if i == 0 else f"page{i + 1}") for i in range(pages)]
        mock_pt.image_to_data.side_effect = side

    return TesseractEngine(_pytesseract=mock_pt)


def _in_memory_engine(*, pages: int = 1, text: str = _IRIS_TEXT) -> InMemoryOCREngine:
    page_results = [
        OCRPageResult(
            page_number=i + 1,
            markdown=text if i == 0 else f"page{i + 1}",
            bboxes=[BBox(x=10, y=10, width=80, height=20)],
            confidence=0.9,
        )
        for i in range(pages)
    ]
    result = OCRResult(
        document_id=_DOC_ID,
        adapter_id="in-memory",
        pages=page_results,
        total_pages=pages,
        total_latency_ms=0,
    )
    return InMemoryOCREngine(responses={_DOC_ID: result}, adapter_id="in-memory")


def _adi_engine_malformed() -> Any:
    """AdiOCREngine whose mock poll returns InvalidContent - simulates server rejection."""
    from iris_ocr_adi import AdiOCREngine

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    post_resp = MagicMock(spec=httpx.Response)
    post_resp.status_code = 202
    post_resp.headers = {"Operation-Location": "https://mock/operations/1"}
    mock_client.post.return_value = post_resp

    poll_resp = MagicMock(spec=httpx.Response)
    poll_resp.status_code = 200
    poll_resp.json.return_value = {
        "status": "failed",
        "error": {"code": "InvalidContent", "message": "The document is not valid."},
    }
    mock_client.get.return_value = poll_resp

    return AdiOCREngine(
        endpoint="https://mock.cognitiveservices.azure.com",
        api_key="test-key",  # pragma: allowlist secret
        poll_interval=0.0,
        _http_client=mock_client,
    )


def _datalab_engine_malformed() -> Any:
    """DatalabOCREngine whose mock POST returns HTTP 400 - simulates server rejection."""
    from iris_ocr_datalab import DatalabOCREngine

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    submit_resp = MagicMock(spec=httpx.Response)
    submit_resp.status_code = 400
    mock_client.post.return_value = submit_resp

    return DatalabOCREngine(
        api_key="test-key",  # pragma: allowlist secret
        poll_interval=0.0,
        _http_client=mock_client,
    )


def _malformed_engine(adapter_id: str) -> Any:
    """Engine configured to reject a malformed document via the appropriate error path.

    HTTP adapters (adi, datalab) validate server-side: the mock returns an error
    response. Inference adapters (paddleocr, local) validate locally via pymupdf.
    """
    if adapter_id == "adi":
        return _adi_engine_malformed()
    if adapter_id == "datalab":
        return _datalab_engine_malformed()
    return _engine(adapter_id)


_FACTORIES: dict[str, Any] = {
    "adi": _adi_engine,
    "datalab": _datalab_engine,
    "paddleocr": _paddleocr_engine,
    "local": _local_engine,
    "in_memory": _in_memory_engine,
}


def _engine(adapter_id: str, **kw: Any) -> Any:
    return _FACTORIES[adapter_id](**kw)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ── C-OCR-001: adapter exposes a stable identifier ───────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c001_id_is_correct(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    assert eng.id == _EXPECTED_IDS[adapter_id]
    if adapter_id != "in_memory":
        assert eng.id in VALID_ADAPTER_IDS


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c001_version_is_semver(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    parts = eng.version.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts)


# ── C-OCR-002: round-trip on a fixture PDF ───────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c002_pdf_extracts_markdown(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    result = _run(eng.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.total_pages == 1
    assert _IRIS_TEXT.lower() in result.pages[0].markdown.lower()


# ── C-OCR-003: multi-page document preserves ordering ────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c003_multipage_ordering(adapter_id: str) -> None:
    eng = _engine(adapter_id, pages=3)
    result = _run(eng.extract(_CTX, _DOC_ID, _make_pdf(num_pages=3), "application/pdf"))
    assert [p.page_number for p in result.pages] == [1, 2, 3]


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c003_page_numbers_start_at_one(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    result = _run(eng.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].page_number == 1


# ── C-OCR-004: bounding box format ───────────────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c004_bbox_non_negative_xy_positive_wh(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    result = _run(eng.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    for page in result.pages:
        for bbox in page.bboxes:
            assert bbox.x >= 0
            assert bbox.y >= 0
            assert bbox.width > 0
            assert bbox.height > 0


# ── C-OCR-005: confidence is in [0, 1] ───────────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c005_confidence_in_range(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    result = _run(eng.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    for page in result.pages:
        assert 0.0 <= page.confidence <= 1.0


# ── C-OCR-006: unsupported content type raises typed error ───────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c006_unsupported_content_type_raises(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    with pytest.raises(OCRUnsupportedContentType):
        _run(eng.extract(_CTX, _DOC_ID, b"data", "application/json"))


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c006_error_does_not_contain_bytes(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    payload = b"sensitive document bytes"
    with pytest.raises(OCRUnsupportedContentType) as exc_info:
        _run(eng.extract(_CTX, _DOC_ID, payload, "text/plain"))
    assert b"sensitive" not in str(exc_info.value).encode()


# ── C-OCR-007: malformed PDF raises typed error ───────────────────────────────
# Excluded from in-memory: InMemoryOCREngine returns pre-registered results
# without parsing the document bytes.


@pytest.mark.parametrize("adapter_id", _CONTENT_VALIDATING)
def test_c007_malformed_pdf_raises_malformed(adapter_id: str) -> None:
    eng = _malformed_engine(adapter_id)
    with pytest.raises(OCRMalformedDocument):
        _run(eng.extract(_CTX, _DOC_ID, b"not a valid pdf", "application/pdf"))


# ── C-OCR-008: empty bytes raises typed error ────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c008_empty_bytes_raises_malformed(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    with pytest.raises(OCRMalformedDocument):
        _run(eng.extract(_CTX, _DOC_ID, b"", "application/pdf"))


# ── C-OCR-009: adapter identifier appears in result ──────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c009_adapter_id_in_result(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    result = _run(eng.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.adapter_id == eng.id


# ── C-OCR-010: image input is accepted ───────────────────────────────────────


@pytest.mark.parametrize("adapter_id", _ALL)
def test_c010_png_input_accepted(adapter_id: str) -> None:
    eng = _engine(adapter_id)
    result = _run(eng.extract(_CTX, _DOC_ID, _make_png(), "image/png"))
    assert result.total_pages >= 1


# ── C-OCR-LOCAL-001: no outbound network access ───────────────────────────────
# Applies to adapters whose extract() never makes network calls: local (Tesseract
# subprocess) and paddleocr (local model inference). Verified by running the full
# extract() path with mocked internals: no real network I/O is possible.


@pytest.mark.parametrize("adapter_id", _LOCAL)
def test_c_ocr_local_001_no_outbound_network(
    adapter_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _deny(*a: object, **k: object) -> None:
        raise AssertionError(f"{adapter_id} adapter attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", _deny)
    result = _run(_engine(adapter_id).extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.total_pages >= 1
    assert result.adapter_id in {"local", "paddleocr"}


# ── C-OCR-011: OTEL span - deferred to T038 ──────────────────────────────────


@pytest.mark.skip(reason="C-OCR-011 (OTEL span with tenant_id) deferred to T038")
def test_c011_otel_span_carries_tenant_id() -> None:
    pass
