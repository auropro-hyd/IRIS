"""Unit tests for PaddleOCREngine - all model inference is mocked.

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
  C-OCR-LOCAL-001  offline mode raises when model path unset
  Initialization, result mapping, image handling
"""

from __future__ import annotations

import asyncio
import io
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pymupdf
import pytest
from iris_engine.contracts.ocr_engine import (
    OCRMalformedDocument,
    OCRUnavailable,
    OCRUnsupportedContentType,
    TenantContext,
)
from iris_ocr_paddleocr import PaddleOCREngine
from PIL import Image

_CTX = TenantContext(tenant_id="tenant-1", product_slug="commercial-auto/in")
_DOC_ID = uuid4()


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ── fixture helpers ────────────────────────────────────────────────────────────


class _MockBlock:
    """Minimal stand-in for a PaddleOCRVLBlock."""

    def __init__(
        self,
        content: str = "IRIS Insurance Reference Intelligence Stack",
        bbox: list[int] | None = None,
        label: str = "text",
    ) -> None:
        self.content = content
        self.bbox = bbox if bbox is not None else [10, 10, 200, 30]
        self.label = label


class _MockResult:
    """Minimal stand-in for a PaddleOCRVLResult (dict-like)."""

    def __init__(self, blocks: list[_MockBlock]) -> None:
        self._blocks = blocks

    def __getitem__(self, key: str) -> Any:
        if key == "parsing_res_list":
            return self._blocks
        raise KeyError(key)


def _result(text: str = "IRIS Insurance Reference Intelligence Stack") -> _MockResult:
    return _MockResult([_MockBlock(content=text)])


def _make_engine(predict_return: list[Any] | None = None) -> tuple[PaddleOCREngine, MagicMock]:
    pipeline = MagicMock()
    pipeline.predict.return_value = predict_return if predict_return is not None else [_result()]
    engine = PaddleOCREngine(_pipeline=pipeline)
    return engine, pipeline


def _make_pdf(
    num_pages: int = 1, text: str = "IRIS Insurance Reference Intelligence Stack"
) -> bytes:
    doc = pymupdf.open()
    for _ in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), text)
    return doc.tobytes()


def _make_png(text: str = "") -> bytes:
    img = Image.new("RGB", (200, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# C-OCR-001 ----------------------------------------------------------------


def test_c001_id_is_paddleocr() -> None:
    engine, _ = _make_engine()
    assert engine.id == "paddleocr"


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
    engine, pipeline = _make_engine()
    pipeline.predict.side_effect = [[_result(f"page {i + 1}")] for i in range(3)]
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


def test_c005_vl_confidence_is_one() -> None:
    """VLM inference produces no per-block confidence scores; adapter returns 1.0."""
    engine, _ = _make_engine()
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].confidence == 1.0


def test_c005_empty_blocks_defaults_to_one() -> None:
    """Empty parsing_res_list means model ran but found nothing; confidence stays 1.0."""
    engine, pipeline = _make_engine()
    pipeline.predict.return_value = [_MockResult([])]
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].confidence == 1.0


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


# C-OCR-LOCAL-001 ----------------------------------------------------------


def test_local_offline_without_model_path_raises_at_init() -> None:
    with pytest.raises(OCRUnavailable, match="IRIS_PADDLEOCR_MODEL_PATH"):
        PaddleOCREngine(offline=True, model_path=None)


def test_local_pipeline_injection_bypasses_model_load() -> None:
    pipeline = MagicMock()
    pipeline.predict.return_value = [_result()]
    engine = PaddleOCREngine(_pipeline=pipeline)
    assert engine.id == "paddleocr"


# Result mapping -----------------------------------------------------------


def test_empty_predict_result_returns_empty_page() -> None:
    engine, pipeline = _make_engine()
    pipeline.predict.return_value = []
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].markdown == ""
    assert result.pages[0].bboxes == []
    assert result.pages[0].confidence == 0.0


def test_multiple_blocks_joined_by_double_newline() -> None:
    engine, pipeline = _make_engine()
    pipeline.predict.return_value = [
        _MockResult(
            [
                _MockBlock(content="line one"),
                _MockBlock(content="line two"),
            ]
        )
    ]
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].markdown == "line one\n\nline two"


def test_missing_parsing_res_list_gives_empty_result() -> None:
    engine, pipeline = _make_engine()
    pipeline.predict.return_value = [object()]  # no __getitem__ -> TypeError -> empty
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].markdown == ""
    assert result.pages[0].bboxes == []


def test_blocks_without_content_are_skipped() -> None:
    engine, pipeline = _make_engine()
    pipeline.predict.return_value = [
        _MockResult(
            [
                _MockBlock(content=""),
                _MockBlock(content="real text"),
            ]
        )
    ]
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    assert result.pages[0].markdown == "real text"


# Bbox conversion ----------------------------------------------------------


def test_rect_to_bbox_min_size_enforced() -> None:
    """A degenerate rect (x1==x2, y1==y2) yields width=height=1."""
    engine, pipeline = _make_engine()
    pipeline.predict.return_value = [_MockResult([_MockBlock(content="x", bbox=[5, 5, 5, 5])])]
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    bbox = result.pages[0].bboxes[0]
    assert bbox.width >= 1
    assert bbox.height >= 1


def test_rect_to_bbox_negative_coords_clamped_to_zero() -> None:
    engine, pipeline = _make_engine()
    pipeline.predict.return_value = [_MockResult([_MockBlock(content="x", bbox=[-5, -3, 50, 20])])]
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(), "application/pdf"))
    bbox = result.pages[0].bboxes[0]
    assert bbox.x >= 0
    assert bbox.y >= 0


# PDF rasterisation --------------------------------------------------------


def test_pdf_total_pages_matches_page_count() -> None:
    engine, pipeline = _make_engine()
    pipeline.predict.side_effect = [[_result(f"p{idx}")] for idx in range(5)]
    result = _run(engine.extract(_CTX, _DOC_ID, _make_pdf(num_pages=5), "application/pdf"))
    assert result.total_pages == 5


def test_malformed_image_bytes_raises_malformed() -> None:
    engine, _ = _make_engine()
    with pytest.raises(OCRMalformedDocument):
        _run(engine.extract(_CTX, _DOC_ID, b"not an image", "image/png"))


def test_zero_page_pdf_raises_malformed() -> None:
    from unittest.mock import patch

    engine, _ = _make_engine()
    mock_doc = MagicMock()
    mock_doc.page_count = 0

    with patch("iris_ocr_paddleocr.client.pymupdf.open", return_value=mock_doc):
        with pytest.raises(OCRMalformedDocument, match="no pages"):
            _run(engine.extract(_CTX, _DOC_ID, b"fake-pdf-bytes", "application/pdf"))


# _load_pipeline -----------------------------------------------------------


def test_load_pipeline_import_error_raises_unavailable() -> None:
    import sys
    from unittest.mock import patch

    from iris_ocr_paddleocr.client import _load_pipeline

    with patch.dict(sys.modules, {"paddleocr": None}):  # type: ignore[dict-item]
        with pytest.raises(OCRUnavailable, match="paddleocr is not installed"):
            _load_pipeline(None, offline=False)


def test_load_pipeline_offline_does_not_mutate_env() -> None:
    import os
    import sys
    from unittest.mock import MagicMock, patch

    from iris_ocr_paddleocr.client import _load_pipeline

    mock_paddleocr_mod = MagicMock()
    mock_paddleocr_mod.PaddleOCRVL = MagicMock()

    with patch.dict(sys.modules, {"paddleocr": mock_paddleocr_mod}):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
            os.environ.pop("HF_DATASETS_OFFLINE", None)
            _load_pipeline("/path/to/model", offline=True)
            assert "TRANSFORMERS_OFFLINE" not in os.environ
            assert "HF_DATASETS_OFFLINE" not in os.environ
