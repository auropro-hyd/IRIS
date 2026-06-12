"""Unit tests for TesseractEngine - all tesseract calls are mocked.

Contract clause coverage:
  C-OCR-001  id / version
  C-OCR-002  fixture PDF extracts markdown
  C-OCR-003  multi-page ordering
  C-OCR-004  bounding box format
  C-OCR-005  confidence in [0, 1]
  C-OCR-006  unsupported content type
  C-OCR-007  malformed PDF
  C-OCR-008  empty bytes
  C-OCR-009  adapter_id in result
  C-OCR-010  PNG input accepted
  C-OCR-LOCAL-001  no outbound network (inherent; tesseract is a local binary)
  Initialization, result mapping, block grouping, bbox conversion
"""

from __future__ import annotations

import asyncio
import io
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pymupdf
import pytest
from iris_engine.contracts.ocr_engine import (
    OCRMalformedDocument,
    OCRUnavailable,
    OCRUnsupportedContentType,
    TenantContext,
)
from iris_ocr_local import TesseractEngine
from PIL import Image

_CTX = TenantContext(tenant_id="tenant-1", product_slug="commercial-auto/in")
_DOC_ID = uuid4()


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ── fixture helpers ────────────────────────────────────────────────────────────


def _mock_data(
    texts: list[str],
    confs: list[int] | None = None,
    block_nums: list[int] | None = None,
    lefts: list[int] | None = None,
    tops: list[int] | None = None,
    widths: list[int] | None = None,
    heights: list[int] | None = None,
) -> dict[str, list[Any]]:
    n = len(texts)
    return {
        "text": texts,
        "conf": confs if confs is not None else [90] * n,
        "block_num": block_nums if block_nums is not None else [1] * n,
        "left": lefts if lefts is not None else [10] * n,
        "top": tops if tops is not None else [10] * n,
        "width": widths if widths is not None else [100] * n,
        "height": heights if heights is not None else [20] * n,
    }


def _make_pytesseract(data: dict[str, list[Any]] | None = None) -> MagicMock:
    mock = MagicMock()
    mock.Output.DICT = "dict"
    default = _mock_data(["IRIS", "Insurance", "Reference", "Intelligence", "Stack"])
    mock.image_to_data.return_value = data if data is not None else default
    return mock


def _make_engine(
    data: dict[str, list[Any]] | None = None,
) -> tuple[TesseractEngine, MagicMock]:
    pt = _make_pytesseract(data)
    engine = TesseractEngine(_pytesseract=pt)
    return engine, pt


def _make_pdf(
    num_pages: int = 1, text: str = "IRIS Insurance Reference Intelligence Stack"
) -> bytes:
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


# C-OCR-001 ----------------------------------------------------------------


def test_c001_id_is_local() -> None:
    engine, _ = _make_engine()
    assert engine.id == "local"


def test_c001_version_is_semver() -> None:
    engine, _ = _make_engine()
    parts = engine.version.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts)


# C-OCR-002 ----------------------------------------------------------------


def test_c002_pdf_extracts_markdown() -> None:
    engine, _ = _make_engine()
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert "iris" in result.pages[0].markdown.lower()


# C-OCR-003 ----------------------------------------------------------------


def test_c003_multipage_ordering() -> None:
    engine, pt = _make_engine()
    pt.image_to_data.side_effect = [_mock_data([f"page{i + 1}"]) for i in range(3)]
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(num_pages=3), "application/pdf"))
    assert [p.page_number for p in result.pages] == [1, 2, 3]


def test_c003_page_numbers_start_at_one() -> None:
    engine, _ = _make_engine()
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].page_number == 1


# C-OCR-004 ----------------------------------------------------------------


def test_c004_bbox_non_negative_xy_positive_wh() -> None:
    engine, _ = _make_engine()
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    for page in result.pages:
        for bbox in page.bboxes:
            assert bbox.x >= 0
            assert bbox.y >= 0
            assert bbox.width > 0
            assert bbox.height > 0


# C-OCR-005 ----------------------------------------------------------------


def test_c005_confidence_in_range() -> None:
    engine, _ = _make_engine()
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    for page in result.pages:
        assert 0.0 <= page.confidence <= 1.0


def test_c005_confidence_is_mean_of_word_scores() -> None:
    engine, _ = _make_engine(_mock_data(["hello", "world"], confs=[80, 60]))
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert abs(result.pages[0].confidence - 0.70) < 0.01


def test_c005_no_words_gives_confidence_zero() -> None:
    engine, _ = _make_engine(_mock_data([], confs=[]))
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].confidence == 0.0


# C-OCR-006 ----------------------------------------------------------------


def test_c006_unsupported_content_type_raises() -> None:
    engine, _ = _make_engine()
    with pytest.raises(OCRUnsupportedContentType):
        _run(engine.extract(_CTX, _DOC_ID, b"data", "application/json"))


def test_c006_error_does_not_contain_bytes() -> None:
    engine, _ = _make_engine()
    payload = b"sensitive document bytes"
    with pytest.raises(OCRUnsupportedContentType) as exc_info:
        _run(engine.extract(_CTX, _DOC_ID, payload, "text/plain"))
    assert b"sensitive" not in str(exc_info.value).encode()


# C-OCR-007 ----------------------------------------------------------------


def test_c007_malformed_pdf_raises_malformed() -> None:
    engine, _ = _make_engine()
    with pytest.raises(OCRMalformedDocument):
        _run(engine.extract(_CTX, _DOC_ID, b"not a valid pdf", "application/pdf"))


# C-OCR-008 ----------------------------------------------------------------


def test_c008_empty_bytes_raises_malformed() -> None:
    engine, _ = _make_engine()
    with pytest.raises(OCRMalformedDocument):
        _run(engine.extract(_CTX, _DOC_ID, b"", "application/pdf"))


# C-OCR-009 ----------------------------------------------------------------


def test_c009_adapter_id_in_result() -> None:
    engine, _ = _make_engine()
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.adapter_id == engine.id


# C-OCR-010 ----------------------------------------------------------------


def test_c010_png_input_accepted() -> None:
    engine, _ = _make_engine()
    result = _run(engine.extract(_CTX, _DOC_ID, _make_png(), "image/png"))
    assert result.total_pages == 1


def test_c010_jpeg_input_accepted() -> None:
    engine, _ = _make_engine()
    buf = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(buf, format="JPEG")
    result = _run(engine.extract(_CTX, _DOC_ID, buf.getvalue(), "image/jpeg"))
    assert result.total_pages == 1


# Initialization -----------------------------------------------------------


def test_import_error_raises_unavailable() -> None:
    import sys

    from iris_ocr_local.client import _load_pytesseract

    with patch.dict(sys.modules, {"pytesseract": None}):  # type: ignore[dict-item]
        with pytest.raises(OCRUnavailable, match="pytesseract is not installed"):
            _load_pytesseract(None)


def test_pipeline_injection_bypasses_load() -> None:
    pt = MagicMock()
    engine = TesseractEngine(_pytesseract=pt)
    assert engine.id == "local"


# Result mapping -----------------------------------------------------------


def test_words_in_same_block_joined_by_space() -> None:
    engine, _ = _make_engine(_mock_data(["foo", "bar", "baz"], block_nums=[1, 1, 1]))
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].markdown == "foo bar baz"


def test_words_from_multiple_blocks_joined_by_double_newline() -> None:
    engine, _ = _make_engine(_mock_data(["hello", "world"], block_nums=[1, 2]))
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].markdown == "hello\n\nworld"


def test_negative_conf_rows_skipped() -> None:
    engine, _ = _make_engine(_mock_data(["layout", "real"], confs=[-1, 90]))
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert "layout" not in result.pages[0].markdown
    assert "real" in result.pages[0].markdown


def test_empty_text_rows_skipped() -> None:
    engine, _ = _make_engine(_mock_data(["", "visible"], confs=[90, 90]))
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].markdown == "visible"


def test_whitespace_only_text_skipped() -> None:
    engine, _ = _make_engine(_mock_data(["   ", "kept"], confs=[90, 90]))
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].markdown == "kept"


# BBox conversion ----------------------------------------------------------


def test_bbox_negative_coords_clamped_to_zero() -> None:
    engine, _ = _make_engine(_mock_data(["x"], lefts=[-5], tops=[-3]))
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    bbox = result.pages[0].bboxes[0]
    assert bbox.x == 0
    assert bbox.y == 0


def test_bbox_degenerate_gets_min_size_one() -> None:
    engine, _ = _make_engine(_mock_data(["x"], widths=[0], heights=[0]))
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    bbox = result.pages[0].bboxes[0]
    assert bbox.width >= 1
    assert bbox.height >= 1


# PDF rasterisation --------------------------------------------------------


def test_pdf_total_pages_matches_page_count() -> None:
    engine, pt = _make_engine()
    pt.image_to_data.side_effect = [_mock_data([f"p{i}"]) for i in range(5)]
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(num_pages=5), "application/pdf"))
    assert result.total_pages == 5


def test_malformed_image_raises_malformed() -> None:
    engine, _ = _make_engine()
    with pytest.raises(OCRMalformedDocument):
        _run(engine.extract(_CTX, _DOC_ID, b"not an image", "image/png"))


def test_zero_page_pdf_raises_malformed() -> None:
    engine, _ = _make_engine()
    mock_doc = MagicMock()
    mock_doc.page_count = 0
    with patch("iris_ocr_local.client.pymupdf.open", return_value=mock_doc):
        with pytest.raises(OCRMalformedDocument, match="no pages"):
            _run(engine.extract(_CTX, _DOC_ID, b"fake", "application/pdf"))
