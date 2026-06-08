"""Unit tests for iris_engine.ocr.selector (T031) and InMemoryOCREngine (T032)."""

import asyncio
from uuid import uuid4

import pytest
from iris_engine.contracts.ocr_engine import (
    OCRMalformedDocument,
    OCRResult,
    OCRUnavailable,
    OCRUnsupportedContentType,
    TenantContext,
)
from iris_engine.ocr.in_memory import InMemoryOCREngine
from iris_engine.ocr.selector import select_ocr_engine

CTX = TenantContext(tenant_id="test-tenant", product_slug="auto/in")
PDF = b"%PDF-1.4 fixture"
PDF_CT = "application/pdf"
PNG_CT = "image/png"


# ── helpers ───────────────────────────────────────────────────────────────────


class _UnavailableEngine:
    """Always raises OCRUnavailable - simulates a failed primary adapter."""

    version = "1.0.0"

    def __init__(self, adapter_id: str = "failing", message: str = "service down") -> None:
        self.id = adapter_id
        self._message = message

    async def extract(self, ctx, document_id, content, content_type) -> OCRResult:
        raise OCRUnavailable(self._message)


def _run(coro):
    return asyncio.run(coro)


# ── T031: selector ────────────────────────────────────────────────────────────


def test_select_returns_primary_engine() -> None:
    engine = InMemoryOCREngine(adapter_id="paddleocr")
    registry = {"paddleocr": engine}
    selected = select_ocr_engine(registry, "paddleocr")
    assert selected is engine


def test_select_no_fallback_returns_engine_directly() -> None:
    engine = InMemoryOCREngine(adapter_id="local")
    registry = {"local": engine}
    selected = select_ocr_engine(registry, "local")
    result = _run(selected.extract(CTX, uuid4(), PDF, PDF_CT))
    assert result.adapter_id == "local"


def test_select_unknown_adapter_raises_key_error() -> None:
    with pytest.raises(KeyError, match="paddleocr"):
        select_ocr_engine({}, "paddleocr")


def test_select_unknown_fallback_raises_key_error() -> None:
    engine = InMemoryOCREngine(adapter_id="paddleocr")
    with pytest.raises(KeyError, match="local"):
        select_ocr_engine({"paddleocr": engine}, "paddleocr", fallback_id="local")


def test_select_primary_success_fallback_not_called() -> None:
    primary = InMemoryOCREngine(adapter_id="paddleocr")
    fallback = InMemoryOCREngine(adapter_id="local")
    registry = {"paddleocr": primary, "local": fallback}
    engine = select_ocr_engine(registry, "paddleocr", fallback_id="local")
    result = _run(engine.extract(CTX, uuid4(), PDF, PDF_CT))
    assert result.adapter_id == "paddleocr"


def test_select_primary_unavailable_fallback_succeeds() -> None:
    primary = _UnavailableEngine(adapter_id="paddleocr")
    fallback = InMemoryOCREngine(adapter_id="local")
    registry = {"paddleocr": primary, "local": fallback}
    engine = select_ocr_engine(registry, "paddleocr", fallback_id="local")
    result = _run(engine.extract(CTX, uuid4(), PDF, PDF_CT))
    assert result.adapter_id == "local"


def test_select_primary_and_fallback_both_fail_surfaces_primary_error() -> None:
    primary = _UnavailableEngine(adapter_id="paddleocr", message="primary down")
    fallback = _UnavailableEngine(adapter_id="local", message="fallback down")
    registry = {"paddleocr": primary, "local": fallback}
    engine = select_ocr_engine(registry, "paddleocr", fallback_id="local")
    with pytest.raises(OCRUnavailable, match="primary down"):
        _run(engine.extract(CTX, uuid4(), PDF, PDF_CT))


def test_select_with_fallback_exposes_primary_id() -> None:
    primary = InMemoryOCREngine(adapter_id="paddleocr")
    fallback = InMemoryOCREngine(adapter_id="local")
    registry = {"paddleocr": primary, "local": fallback}
    engine = select_ocr_engine(registry, "paddleocr", fallback_id="local")
    assert engine.id == "paddleocr"


# ── T032: InMemoryOCREngine ───────────────────────────────────────────────────


def test_inmemory_returns_ocr_result() -> None:
    engine = InMemoryOCREngine()
    result = _run(engine.extract(CTX, uuid4(), PDF, PDF_CT))
    assert isinstance(result, OCRResult)


def test_inmemory_adapter_id_in_result() -> None:
    engine = InMemoryOCREngine(adapter_id="paddleocr")
    result = _run(engine.extract(CTX, uuid4(), PDF, PDF_CT))
    assert result.adapter_id == "paddleocr"


def test_inmemory_document_id_in_result() -> None:
    engine = InMemoryOCREngine()
    doc_id = uuid4()
    result = _run(engine.extract(CTX, doc_id, PDF, PDF_CT))
    assert result.document_id == doc_id


def test_inmemory_default_result_has_one_page() -> None:
    engine = InMemoryOCREngine()
    result = _run(engine.extract(CTX, uuid4(), PDF, PDF_CT))
    assert result.total_pages == 1
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1


def test_inmemory_returns_canned_response() -> None:
    doc_id = uuid4()
    canned = OCRResult(
        document_id=doc_id,
        adapter_id="paddleocr",
        pages=[],
        total_pages=3,
        total_latency_ms=42,
    )
    engine = InMemoryOCREngine(responses={doc_id: canned})
    result = _run(engine.extract(CTX, doc_id, PDF, PDF_CT))
    assert result is canned


def test_inmemory_unknown_document_id_returns_default() -> None:
    engine = InMemoryOCREngine()
    result = _run(engine.extract(CTX, uuid4(), PDF, PDF_CT))
    assert result.total_pages == 1


def test_inmemory_unsupported_content_type_raises_typed_error() -> None:
    engine = InMemoryOCREngine()
    with pytest.raises(OCRUnsupportedContentType):
        _run(engine.extract(CTX, uuid4(), b"data", "application/json"))


def test_inmemory_empty_content_raises_typed_error() -> None:
    engine = InMemoryOCREngine()
    with pytest.raises(OCRMalformedDocument):
        _run(engine.extract(CTX, uuid4(), b"", PDF_CT))


def test_inmemory_accepts_png_content_type() -> None:
    engine = InMemoryOCREngine()
    result = _run(engine.extract(CTX, uuid4(), b"PNG data", PNG_CT))
    assert isinstance(result, OCRResult)


def test_inmemory_default_adapter_id_is_in_memory() -> None:
    engine = InMemoryOCREngine()
    assert engine.id == "in-memory"
