"""Live integration test for TesseractEngine.

Runs against the real tesseract binary installed on this machine.
Gated on IRIS_OCR_LIVE_LOCAL=1.

System prerequisite:
  Linux:   sudo apt install tesseract-ocr tesseract-ocr-eng
  macOS:   brew install tesseract
  Windows: choco install tesseract
           Set IRIS_TESSERACT_CMD if tesseract.exe is not on PATH.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pymupdf
import pytest
from iris_engine.contracts.ocr_engine import TenantContext
from iris_ocr_local import TesseractEngine

_LIVE = os.getenv("IRIS_OCR_LIVE_LOCAL")

pytestmark = [
    pytest.mark.skipif(not _LIVE, reason="IRIS_OCR_LIVE_LOCAL not set"),
    pytest.mark.slow,
]


def _make_pdf(text: str = "IRIS live test") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=24)
    return doc.tobytes()


def test_live_pdf_round_trip() -> None:
    engine = TesseractEngine()
    ctx = TenantContext(tenant_id="live-test", product_slug="test/live")
    content = _make_pdf("IRIS live test")

    result = asyncio.run(engine.extract(ctx, uuid4(), content, "application/pdf"))

    assert result.total_pages == 1
    assert result.adapter_id == "local"
    assert result.pages[0].confidence > 0.0
    assert len(result.pages[0].bboxes) > 0
    assert "iris" in result.pages[0].markdown.lower()

    print(f"\nadapter_id : {result.adapter_id}")
    print(f"total_pages: {result.total_pages}")
    print(f"latency_ms : {result.total_latency_ms}")
    print(f"confidence : {result.pages[0].confidence:.4f}")
    print(f"bboxes     : {len(result.pages[0].bboxes)}")
    print(f"markdown   : {result.pages[0].markdown!r}")
