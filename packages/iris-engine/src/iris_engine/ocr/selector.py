"""OCR adapter selector.

Reads adapter IDs from Product config strings and returns the registered
OCREngine instance. Wraps the engine in fallback logic when ocr_fallback
is configured.

iris_engine sits at the bottom import layer and must not import iris_config.
Callers (iris_agents, iris_api) extract the adapter ID strings from
ProductConfig and pass them here.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from iris_engine.contracts.ocr_engine import (
    OCREngine,
    OCRResult,
    OCRUnavailable,
    TenantContext,
)


def select_ocr_engine(
    registry: Mapping[str, OCREngine],
    adapter_id: str,
    fallback_id: str | None = None,
) -> OCREngine:
    """Return the OCREngine for adapter_id, optionally wrapped with fallback.

    Args:
        registry: mapping of adapter ID strings to OCREngine instances.
        adapter_id: value of ProductConfig.adapters.ocr.
        fallback_id: value of ProductConfig.adapters.ocr_fallback, or None.

    Raises:
        KeyError: adapter_id or fallback_id not present in registry.
    """
    if adapter_id not in registry:
        raise KeyError(f"OCR adapter {adapter_id!r} not in registry")
    primary = registry[adapter_id]
    if fallback_id is None:
        return primary
    if fallback_id not in registry:
        raise KeyError(f"OCR fallback adapter {fallback_id!r} not in registry")
    return _FallbackOCREngine(primary, registry[fallback_id])


class _FallbackOCREngine:
    """Wraps a primary engine with a fallback for OCRUnavailable failures."""

    def __init__(self, primary: OCREngine, fallback: OCREngine) -> None:
        self.id = primary.id
        self.version = primary.version
        self._primary = primary
        self._fallback = fallback

    async def extract(
        self,
        ctx: TenantContext,
        document_id: UUID,
        content: bytes,
        content_type: str,
    ) -> OCRResult:
        try:
            return await self._primary.extract(ctx, document_id, content, content_type)
        except OCRUnavailable as primary_exc:
            try:
                return await self._fallback.extract(ctx, document_id, content, content_type)
            except OCRUnavailable:
                raise primary_exc from None
