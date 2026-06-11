"""PaddleOCR VL 1.6 local OCR adapter for IRIS.

Model: PaddlePaddle/PaddleOCR-VL-1.6 (1B VLM, Apache 2.0).
Inference: paddleocr library - PaddleOCRVL pipeline returning structured output
with bounding boxes, per-word recognition text, and confidence scores.
The transformers path is not used because it returns raw text with no bbox structure.

PDF handling: PyMuPDF rasterises each PDF page to a PIL Image at _DEFAULT_DPI
(150 DPI) before inference. PNG, JPEG, and TIFF inputs are decoded by Pillow.
Multi-frame TIFF is supported; each frame becomes a page.

GPU + CPU: the paddleocr library selects CUDA automatically when available.
No explicit device argument is needed.

Offline mode (IRIS_PADDLEOCR_OFFLINE=1): passes IRIS_PADDLEOCR_MODEL_PATH as
the local snapshot directory to PaddleOCRVL instead of the HuggingFace model ID.
If IRIS_PADDLEOCR_OFFLINE=1 but IRIS_PADDLEOCR_MODEL_PATH is unset, the adapter
raises OCRUnavailable at construction time rather than hanging at first use.

For fully airgapped deployments, also set TRANSFORMERS_OFFLINE=1 and
HF_DATASETS_OFFLINE=1 in the process environment (via .env) so the HuggingFace
libraries do not attempt any network calls. This adapter does not set those vars
programmatically - they are deployment-level configuration, not adapter state.
"""

from __future__ import annotations

import io
import time
from typing import Any
from uuid import UUID

import numpy as np
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

_HF_MODEL_ID = "PaddlePaddle/PaddleOCR-VL-1.6"
_PIPELINE_VERSION = "v1.6"
_DEFAULT_DPI = 150


class PaddleOCREngine:
    id: str = "paddleocr"
    version: str = "1.0.0"

    def __init__(
        self,
        *,
        offline: bool = False,
        model_path: str | None = None,
        dpi: int = _DEFAULT_DPI,
        _pipeline: Any | None = None,
    ) -> None:
        self._dpi = dpi
        if _pipeline is not None:
            # Injection seam: bypasses model loading entirely for unit tests.
            self._pipeline = _pipeline
            return
        if offline and not model_path:
            raise OCRUnavailable(
                "IRIS_PADDLEOCR_OFFLINE=1 requires IRIS_PADDLEOCR_MODEL_PATH to be set"
            )
        self._pipeline = _load_pipeline(model_path, offline=offline)

    async def extract(
        self,
        ctx: TenantContext,
        document_id: UUID,
        content: bytes,
        content_type: str,
    ) -> OCRResult:
        if content_type not in VALID_CONTENT_TYPES:
            raise OCRUnsupportedContentType(
                f"PaddleOCR adapter does not support content type {content_type!r}"
            )
        if not content:
            raise OCRMalformedDocument("content is empty")

        start = time.monotonic()
        images = _to_images(content, content_type, self._dpi)
        ocr_pages = [
            _run_page(self._pipeline, img, page_number=i + 1) for i, img in enumerate(images)
        ]
        elapsed_ms = int((time.monotonic() - start) * 1000)

        return OCRResult(
            document_id=document_id,
            adapter_id=self.id,
            pages=ocr_pages,
            total_pages=len(ocr_pages),
            total_latency_ms=elapsed_ms,
        )


def _load_pipeline(model_path: str | None, offline: bool) -> Any:
    try:
        from paddleocr import PaddleOCRVL  # type: ignore[import-untyped]
    except ImportError as exc:
        raise OCRUnavailable(
            "paddleocr is not installed; run: pip install 'paddleocr[doc-parser]>=3.6.0'"
        ) from exc

    if offline and model_path:
        # vl_rec_model_dir points the VL recognition sub-module to a local HF snapshot.
        # Layout-detection and doc-preprocessor sub-models still download from PaddlePaddle
        # on first use unless their model dirs are also supplied.
        return PaddleOCRVL(pipeline_version=_PIPELINE_VERSION, vl_rec_model_dir=model_path)
    return PaddleOCRVL(pipeline_version=_PIPELINE_VERSION)


def _to_images(content: bytes, content_type: str, dpi: int) -> list[Image.Image]:
    if content_type == "application/pdf":
        try:
            doc = pymupdf.open(stream=content, filetype="pdf")  # type: ignore[no-untyped-call]  # pymupdf stub gap
        except Exception as exc:
            raise OCRMalformedDocument(f"Cannot open PDF: {exc}") from exc
        with doc:
            if doc.page_count == 0:
                raise OCRMalformedDocument("PDF contains no pages")
            mat = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)  # type: ignore[no-untyped-call]  # pymupdf stub gap
            images: list[Image.Image] = []
            for page in doc:  # type: ignore[attr-defined]  # Document iterates via __getitem__; stub missing __iter__
                pix = page.get_pixmap(matrix=mat)
                images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        return images

    # PNG, JPEG, TIFF: decode with Pillow; handle multi-frame (e.g. multi-page TIFF).
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


def _run_page(pipeline: Any, image: Image.Image, page_number: int) -> OCRPageResult:
    img_array: Any = np.array(image)
    results: list[Any] = pipeline.predict(img_array)
    if not results:
        return OCRPageResult(page_number=page_number, markdown="", bboxes=[], confidence=0.0)
    return _map_result(results[0], page_number)


def _map_result(res: Any, page_number: int) -> OCRPageResult:
    """Map one PaddleOCRVLResult to OCRPageResult.

    PaddleOCRVLResult is dict-like. res["parsing_res_list"] is a list of
    PaddleOCRVLBlock objects, each with .label, .bbox ([x1,y1,x2,y2]), .content.
    The VLM produces no per-block confidence score, so confidence is fixed at 1.0.
    """
    try:
        blocks: list[Any] = list(res["parsing_res_list"] or [])
    except (KeyError, TypeError):
        blocks = []

    texts = [b.content for b in blocks if getattr(b, "content", None)]
    bboxes = [_rect_to_bbox(b.bbox) for b in blocks if getattr(b, "bbox", None)]
    markdown = "\n\n".join(texts)

    return OCRPageResult(
        page_number=page_number,
        markdown=markdown,
        bboxes=bboxes,
        confidence=1.0,
    )


def _rect_to_bbox(bbox: Any) -> BBox:
    """Convert [x1, y1, x2, y2] axis-aligned bbox from PaddleOCR-VL to BBox."""
    x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
    return BBox(
        x=max(0, x1),
        y=max(0, y1),
        width=max(1, x2 - x1),
        height=max(1, y2 - y1),
    )
