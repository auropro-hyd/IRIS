# Contract: OCREngine

This contract defines the Protocol every OCR adapter implements. The contract test suite (workstream task T037) verifies each adapter against every clause below.

## Types

```python
from typing import Protocol, Literal, Sequence
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class BBox:
    """A single bounding box on a page. Coordinates in pixels from the top-left."""
    x: int
    y: int
    width: int
    height: int

@dataclass(frozen=True)
class OCRPageResult:
    page_number: int             # 1-indexed
    markdown: str
    bboxes: Sequence[BBox]
    confidence: float            # 0.0 to 1.0; per-page mean

@dataclass(frozen=True)
class OCRResult:
    document_id: UUID
    adapter_id: str              # "adi" | "datalab" | "paddleocr" | "local"
    pages: Sequence[OCRPageResult]
    total_pages: int
    total_latency_ms: int

class OCREngine(Protocol):
    id: str                      # adapter identifier; matches the bundle's adapters.ocr
    version: str

    async def extract(
        self,
        ctx: TenantContext,
        document_id: UUID,
        content: bytes,
        content_type: str,       # "application/pdf", "image/png", "image/jpeg", "image/tiff"
    ) -> OCRResult: ...
```

## Errors

Every adapter raises one of these typed errors. Generic exceptions are not acceptable.

```python
class OCRError(Exception): ...
class OCRUnavailable(OCRError): ...                # network failure, 5xx, timeout
class OCRRateLimited(OCRError): ...                # 429 or provider-specific quota
class OCRUnsupportedContentType(OCRError): ...     # adapter cannot handle this MIME type
class OCRDocumentTooLarge(OCRError): ...
class OCRAuthenticationFailed(OCRError): ...       # bad API key, expired token
class OCRMalformedDocument(OCRError): ...          # corrupt PDF, unreadable bytes
```

## Contract clauses

The test suite asserts each of these clauses against every registered adapter.

### C-OCR-001 Adapter exposes a stable identifier

The `id` attribute matches one of `adi`, `datalab`, `paddleocr`, `local`. The `version` attribute is a semver string.

### C-OCR-002 Round-trip on a fixture PDF

Given a one-page fixture PDF containing the text "IRIS Insurance Reference Intelligence Stack", `extract` returns an `OCRResult` with `total_pages == 1` and `pages[0].markdown` containing the source string (case-insensitive substring match accepted).

### C-OCR-003 Multi-page document preserves ordering

Given a three-page fixture PDF, `extract` returns pages ordered by `page_number` ascending, with `page_number` values `[1, 2, 3]`.

### C-OCR-004 Bounding box format

Every `BBox` has non-negative `x` and `y` and strictly positive `width` and `height`. Coordinates are in pixels relative to the top-left.

### C-OCR-005 Confidence is in `[0, 1]`

Every page's `confidence` is a float between zero and one inclusive.

### C-OCR-006 Unsupported content type raises typed error

Calling `extract` with `content_type="application/json"` raises `OCRUnsupportedContentType`. The error does not leak the document bytes in its message.

### C-OCR-007 Malformed PDF raises typed error

Calling `extract` with `content_type="application/pdf"` and bytes that are not a valid PDF (random bytes) raises `OCRMalformedDocument`.

### C-OCR-008 Empty bytes raises typed error

Calling `extract` with `content=b""` raises `OCRMalformedDocument`.

### C-OCR-009 Adapter identifier appears in result

`result.adapter_id == adapter.id`.

### C-OCR-010 Image input is accepted

Given a PNG fixture, `extract` returns an `OCRResult` with `total_pages == 1`.

### C-OCR-011 Tenant context is preserved end-to-end

The OTEL span emitted by `extract` carries `tenant_id` matching `ctx.tenant_id`.

## Local adapter additional clauses

### C-OCR-LOCAL-001 No outbound network access

Running the local adapter with all sockets restricted to `localhost` produces a valid `OCRResult`. No DNS lookups, no outbound connections.

## Live adapter additional clauses

The live clauses run only when the corresponding environment variable is set.

### C-OCR-LIVE-001 Round-trip against the real endpoint

`IRIS_OCR_LIVE_<ADAPTER>=1` enables a single live extraction against a small fixture. The result matches the same shape as the unit clauses.
