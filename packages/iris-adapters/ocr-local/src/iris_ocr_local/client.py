"""Tesseract local OCR adapter for IRIS.

Wraps pytesseract (a thin Python wrapper around the tesseract binary).
No network calls are ever made; C-OCR-LOCAL-001 is satisfied unconditionally.

System prerequisite: the tesseract binary must be installed at the OS level
(apt/brew/choco). pytesseract itself is a Python package installed by uv.

PDF handling: PyMuPDF rasterises each PDF page to a PIL Image at _DEFAULT_DPI
(150 DPI) before inference. PNG, JPEG, and TIFF inputs are decoded by Pillow.

Confidence: pytesseract.image_to_data() returns per-word conf in [0, 100].
The adapter normalises to [0.0, 1.0] and averages across valid words per page.
Pages with no detected words return confidence=0.0.

Binary path: if IRIS_TESSERACT_CMD is set, it overrides pytesseract.tesseract_cmd
before inference. Useful on Windows where the binary is not on PATH.
"""

from __future__ import annotations

import io
import os
import time
from typing import Any
from uuid import UUID

import pymupdf
from iris_engine.contracts.ocr_engine import (
    VALID_CONTENT_TYPES,
    BBox,
    OCRMalformedDocument,
    OCRPageResult,
    OCRResult,
    OCRUnavailable,
    OCRUnsupportedContentType,
    TenantContext,
)
from PIL import Image

_DEFAULT_DPI = 150


class TesseractEngine:
    id: str = "local"
    version: str = "1.0.0"

    def __init__(
        self,
        *,
        dpi: int = _DEFAULT_DPI,
        tesseract_cmd: str | None = None,
        _pytesseract: Any | None = None,
    ) -> None:
        self._dpi = dpi
        if _pytesseract is not None:
            # Injection seam: bypasses binary detection entirely for unit tests.
            self._pytesseract = _pytesseract
            return
        self._pytesseract = _load_pytesseract(tesseract_cmd)

    async def extract(
        self,
        ctx: TenantContext,
        document_id: UUID,
        content: bytes,
        content_type: str,
    ) -> OCRResult:
        if content_type not in VALID_CONTENT_TYPES:
            raise OCRUnsupportedContentType(
                f"Tesseract adapter does not support content type {content_type!r}"
            )
        if not content:
            raise OCRMalformedDocument("content is empty")

        start = time.monotonic()
        images = _to_images(content, content_type, self._dpi)
        ocr_pages = [
            _run_page(self._pytesseract, img, page_number=i + 1) for i, img in enumerate(images)
        ]
        elapsed_ms = int((time.monotonic() - start) * 1000)

        return OCRResult(
            document_id=document_id,
            adapter_id=self.id,
            pages=ocr_pages,
            total_pages=len(ocr_pages),
            total_latency_ms=elapsed_ms,
        )


def _load_pytesseract(tesseract_cmd: str | None) -> Any:
    try:
        import pytesseract  # type: ignore[import-untyped]
    except ImportError as exc:
        raise OCRUnavailable("pytesseract is not installed; run: pip install pytesseract") from exc

    cmd = tesseract_cmd or os.environ.get("IRIS_TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd

    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise OCRUnavailable(
            "tesseract binary not found; install tesseract-ocr and set "
            "IRIS_TESSERACT_CMD if it is not on PATH"
        ) from exc

    return pytesseract


def _to_images(content: bytes, content_type: str, dpi: int) -> list[Image.Image]:
    if content_type == "application/pdf":
        try:
            doc = pymupdf.open(stream=content, filetype="pdf")  # type: ignore[no-untyped-call]
        except Exception as exc:
            raise OCRMalformedDocument(f"Cannot open PDF: {exc}") from exc
        with doc:
            if doc.page_count == 0:
                raise OCRMalformedDocument("PDF contains no pages")
            mat = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)  # type: ignore[no-untyped-call]
            images: list[Image.Image] = []
            for page in doc:  # type: ignore[attr-defined]
                pix = page.get_pixmap(matrix=mat)
                images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        return images

    try:
        pil_img = Image.open(io.BytesIO(content))
    except Exception as exc:
        raise OCRMalformedDocument(f"Cannot open image: {exc}") from exc

    frames: list[Image.Image] = []
    try:
        while True:
            frames.append(pil_img.copy().convert("RGB"))
            pil_img.seek(pil_img.tell() + 1)
    except (EOFError, AttributeError):
        pass
    return frames if frames else [pil_img.convert("RGB")]


def _run_page(pytesseract: Any, image: Image.Image, page_number: int) -> OCRPageResult:
    try:
        data: dict[str, list[Any]] = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT
        )
    except Exception as exc:
        raise OCRUnavailable(f"Tesseract inference failed: {exc}") from exc
    return _map_result(data, page_number)


def _map_result(data: dict[str, list[Any]], page_number: int) -> OCRPageResult:
    """Map pytesseract image_to_data output to OCRPageResult.

    Rows with conf == -1 are layout rows (block/line headers), not words - skipped.
    Words with empty text after strip are also skipped.
    Words are grouped by block_num; blocks are joined with double newline.
    """
    n = len(data.get("text", []))
    if n == 0:
        return OCRPageResult(page_number=page_number, markdown="", bboxes=[], confidence=0.0)

    blocks: dict[int, list[str]] = {}
    bboxes: list[BBox] = []
    confidences: list[float] = []

    for i in range(n):
        conf = int(data["conf"][i])
        text = str(data["text"][i]).strip()
        if conf < 0 or not text:
            continue
        block = int(data["block_num"][i])
        blocks.setdefault(block, []).append(text)
        bboxes.append(
            BBox(
                x=max(0, int(data["left"][i])),
                y=max(0, int(data["top"][i])),
                width=max(1, int(data["width"][i])),
                height=max(1, int(data["height"][i])),
            )
        )
        confidences.append(conf / 100.0)

    markdown = "\n\n".join(" ".join(words) for words in blocks.values())
    confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return OCRPageResult(
        page_number=page_number,
        markdown=markdown,
        bboxes=bboxes,
        confidence=confidence,
    )
