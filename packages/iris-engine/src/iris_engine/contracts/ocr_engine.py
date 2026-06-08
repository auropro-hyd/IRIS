"""OCREngine Protocol, result types, and typed errors.

No adapter imports. This module must remain importable without any OCR
dependency installed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

# ── shared context ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    product_slug: str


# ── result types ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BBox:
    """Bounding box on a page. Coordinates in pixels from the top-left."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class OCRPageResult:
    page_number: int  # 1-indexed
    markdown: str
    bboxes: Sequence[BBox]
    confidence: float  # 0.0 – 1.0 per-page mean


@dataclass(frozen=True)
class OCRResult:
    document_id: UUID
    adapter_id: str  # "adi" | "datalab" | "paddleocr" | "local"
    pages: Sequence[OCRPageResult]
    total_pages: int
    total_latency_ms: int


# ── error hierarchy ───────────────────────────────────────────────────────────


class OCRError(Exception):
    """Base for all typed OCR errors."""


class OCRUnavailable(OCRError):
    """Network failure, 5xx, or timeout."""


class OCRRateLimited(OCRError):
    """429 or provider-specific quota exceeded."""


class OCRUnsupportedContentType(OCRError):
    """Adapter cannot handle the given MIME type."""


class OCRDocumentTooLarge(OCRError):
    """Document exceeds the adapter's size limit."""


class OCRAuthenticationFailed(OCRError):
    """Bad API key or expired token."""


class OCRMalformedDocument(OCRError):
    """Corrupt PDF, empty bytes, or otherwise unreadable content."""


# ── Protocol ──────────────────────────────────────────────────────────────────

VALID_CONTENT_TYPES: frozenset[str] = frozenset(
    {"application/pdf", "image/png", "image/jpeg", "image/tiff"}
)

VALID_ADAPTER_IDS: frozenset[str] = frozenset({"adi", "datalab", "paddleocr", "local"})


class OCREngine(Protocol):
    id: str  # adapter identifier; must be one of VALID_ADAPTER_IDS
    version: str  # semver string

    async def extract(
        self,
        ctx: TenantContext,
        document_id: UUID,
        content: bytes,
        content_type: str,
    ) -> OCRResult:
        """Extract text from a document.

        Raises:
            OCRUnsupportedContentType: content_type not in VALID_CONTENT_TYPES.
            OCRMalformedDocument: content is empty or not a valid document.
            OCRUnavailable: network or service failure.
            OCRRateLimited: quota exceeded.
            OCRAuthenticationFailed: bad credentials.
            OCRDocumentTooLarge: document exceeds adapter limit.
        """
        ...
