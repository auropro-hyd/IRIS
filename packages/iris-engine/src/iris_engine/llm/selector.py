"""LLM provider selector.

Reads adapter IDs from Product config strings and returns the registered
LLMProvider instance. Wraps the provider in fallback logic when llm_fallback
is configured.

iris_engine sits at the bottom import layer and must not import iris_config.
Callers (iris_agents, iris_api) extract the adapter ID strings from
ProductConfig and pass them here.
"""

from __future__ import annotations

from collections.abc import Mapping

from iris_engine.contracts.llm_provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMUnavailable,
    TenantContext,
)


def select_llm_provider(
    registry: Mapping[str, LLMProvider],
    adapter_id: str,
    fallback_id: str | None = None,
) -> LLMProvider:
    """Return the LLMProvider for adapter_id, optionally wrapped with fallback.

    Args:
        registry: mapping of adapter ID strings to LLMProvider instances.
        adapter_id: value of ProductConfig.adapters.llm.
        fallback_id: value of ProductConfig.adapters.llm_fallback, or None.

    Raises:
        KeyError: adapter_id or fallback_id not present in registry.
    """
    if adapter_id not in registry:
        raise KeyError(f"LLM adapter {adapter_id!r} not in registry")
    primary = registry[adapter_id]
    if fallback_id is None:
        return primary
    if fallback_id not in registry:
        raise KeyError(f"LLM fallback adapter {fallback_id!r} not in registry")
    return _FallbackLLMProvider(primary, registry[fallback_id])


class _FallbackLLMProvider:
    """Wraps a primary provider with a fallback for LLMUnavailable failures.

    Fallback fires only on LLMUnavailable (network/service failure).
    LLMRateLimited surfaces to the caller for backoff/retry instead; rate
    limiting on the primary does not mean the fallback can handle the load.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.id = primary.id
        self.version = primary.version
        self._primary = primary
        self._fallback = fallback

    async def complete(
        self,
        ctx: TenantContext,
        request: LLMRequest,
    ) -> LLMResponse:
        try:
            return await self._primary.complete(ctx, request)
        except LLMUnavailable as primary_exc:
            try:
                return await self._fallback.complete(ctx, request)
            except LLMUnavailable:
                raise primary_exc from None
