"""Live tests for PaddleOCREngine.

Gated on IRIS_OCR_LIVE_PADDLEOCR=1. Requires:
  - paddleocr[doc-parser]>=3.6.0 installed
  - Model downloaded (online) OR IRIS_PADDLEOCR_OFFLINE=1 + IRIS_PADDLEOCR_MODEL_PATH set

Run:
  IRIS_OCR_LIVE_PADDLEOCR=1 uv run pytest \
      packages/iris-adapters/ocr-paddleocr/tests/test_live.py -m ""
"""

from __future__ import annotations

import io
import os
from uuid import uuid4

import pytest
from iris_engine.contracts.ocr_engine import TenantContext
from iris_ocr_paddleocr import PaddleOCREngine
from PIL import Image

_LIVE = os.getenv("IRIS_OCR_LIVE_PADDLEOCR") == "1"
_OFFLINE = os.getenv("IRIS_PADDLEOCR_OFFLINE") == "1"
_MODEL_PATH = os.getenv("IRIS_PADDLEOCR_MODEL_PATH")

pytestmark = [
    pytest.mark.skipif(not _LIVE, reason="IRIS_OCR_LIVE_PADDLEOCR not set"),
    pytest.mark.slow,
]

_CTX = TenantContext(tenant_id="live-tenant", product_slug="commercial-auto/in")


def _make_png_fixture() -> bytes:
    img = Image.new("RGB", (400, 100), color="white")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "IRIS live test", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# C-OCR-LIVE-001 -----------------------------------------------------------


def test_live_png_round_trip() -> None:
    """C-OCR-LIVE-001: round-trip against real PaddleOCR model with a PNG fixture."""
    engine = PaddleOCREngine(
        offline=_OFFLINE,
        model_path=_MODEL_PATH if _OFFLINE else None,
    )
    import asyncio

    result = asyncio.run(engine.extract(_CTX, uuid4(), _make_png_fixture(), "image/png"))

    print(f"\nadapter_id  : {result.adapter_id}")
    print(f"total_pages : {result.total_pages}")
    print(f"latency_ms  : {result.total_latency_ms}")
    for page in result.pages:
        print(f"\n--- page {page.page_number} ---")
        print(f"confidence  : {page.confidence:.4f}")
        print(f"bboxes      : {len(page.bboxes)}")
        print(f"markdown    :\n{page.markdown}")

    assert result.adapter_id == "paddleocr"
    assert result.total_pages >= 1
    assert all(0.0 <= p.confidence <= 1.0 for p in result.pages)
    assert all(
        b.x >= 0 and b.y >= 0 and b.width > 0 and b.height > 0
        for p in result.pages
        for b in p.bboxes
    )
