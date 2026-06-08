"""OCR selector and in-memory engine."""

from iris_engine.ocr.in_memory import InMemoryOCREngine
from iris_engine.ocr.selector import select_ocr_engine

__all__ = ["InMemoryOCREngine", "select_ocr_engine"]
