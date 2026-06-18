"""Exponential backoff retry helper for OpenAI-compatible LLM adapters."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from iris_engine.contracts.llm_provider import LLMRateLimited, LLMUnavailable

_RETRYABLE = (LLMRateLimited, LLMUnavailable)


@dataclass(frozen=True)
class RetryConfig:
    max_retries: int = 3
    backoff_ms: int = 500

    @classmethod
    def from_params(cls, max_retries: int, retry_backoff_ms: int) -> RetryConfig:
        return cls(max_retries=max_retries, backoff_ms=retry_backoff_ms)


async def with_retry[T](coro_fn: Callable[[], Coroutine[Any, Any, T]], config: RetryConfig) -> T:
    """Call coro_fn(), retrying on LLMRateLimited or LLMUnavailable.

    Waits config.backoff_ms * 2^attempt milliseconds between retries.
    Re-raises the last error after config.max_retries attempts.
    """
    last_exc: Exception | None = None
    for attempt in range(config.max_retries + 1):
        try:
            return await coro_fn()
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt == config.max_retries:
                break
            delay = config.backoff_ms * (2**attempt) / 1000.0
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]
