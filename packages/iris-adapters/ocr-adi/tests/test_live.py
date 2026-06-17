"""Live integration tests for AdiOCREngine.

Runs only when IRIS_OCR_LIVE_ADI=1 and ADI credentials are configured.
Required env vars:
  IRIS_ADI_ENDPOINT  - e.g. https://{resource}.cognitiveservices.azure.com
  IRIS_ADI_API_KEY   - subscription key

C-OCR-LIVE-001: round-trip against the real ADI endpoint with a fixture PDF.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from iris_engine.contracts.ocr_engine import TenantContext
from iris_ocr_adi import AdiOCREngine

pytestmark = [
    pytest.mark.skipif(not os.getenv("IRIS_OCR_LIVE_ADI"), reason="IRIS_OCR_LIVE_ADI not set"),
    pytest.mark.slow,
]

_CTX = TenantContext(tenant_id="live-test", product_slug="test/live")

# Minimal valid single-page PDF - enough to verify the live round-trip.
_FIXTURE_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
    b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 44>>stream\n"
    b"BT /F1 12 Tf 100 700 Td (IRIS live test) Tj ET\n"
    b"endstream\nendobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"xref\n0 6\n"
    b"0000000000 65535 f \n"
    b"trailer<</Size 6/Root 1 0 R>>\n"
    b"startxref\n9\n%%EOF"
)


def test_live_c_ocr_live_001_round_trip():
    """C-OCR-LIVE-001: single document extraction against the real ADI endpoint."""
    engine = AdiOCREngine(
        endpoint=os.environ["IRIS_ADI_ENDPOINT"],
        api_key=os.environ["IRIS_ADI_API_KEY"],
    )
    result = asyncio.run(engine.extract(_CTX, uuid4(), _FIXTURE_PDF, "application/pdf"))

    assert result.total_pages >= 1
    assert result.adapter_id == "adi"
    for page in result.pages:
        assert 0.0 <= page.confidence <= 1.0
        assert isinstance(page.markdown, str)
