"""LLMProvider Protocol, request/response types, and typed errors.

No adapter imports. This module must remain importable without any LLM
dependency installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from iris_engine.contracts.ocr_engine import TenantContext

__all__ = [
    "VALID_ADAPTER_IDS",
    "LLMError",
    "LLMUnavailable",
    "LLMRateLimited",
    "LLMAuthenticationFailed",
    "LLMSchemaViolation",
    "LLMContextWindowExceeded",
    "LLMContentFiltered",
    "LLMInvalidRequest",
    "LLMUsage",
    "LLMResponse",
    "LLMRequest",
    "LLMProvider",
    "TenantContext",
]

VALID_ADAPTER_IDS: frozenset[str] = frozenset({"azure-openai", "openai", "anthropic", "local"})


# ── error hierarchy ───────────────────────────────────────────────────────────


class LLMError(Exception):
    """Base for all typed LLM errors."""


class LLMUnavailable(LLMError):
    """Network failure, 5xx, or timeout."""


class LLMRateLimited(LLMError):
    """429 or quota exhausted."""


class LLMAuthenticationFailed(LLMError):
    """401 or 403; invalid or expired credentials."""


class LLMSchemaViolation(LLMError):
    """Structured output did not match the requested schema."""


class LLMContextWindowExceeded(LLMError):
    """Prompt + max_output_tokens exceeds the model context limit."""


class LLMContentFiltered(LLMError):
    """Provider content policy blocked the request."""


class LLMInvalidRequest(LLMError):
    """400 from the provider; request is malformed."""


# ── data types ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int  # must equal input_tokens + output_tokens


@dataclass(frozen=True)
class LLMResponse:
    text: str
    structured: BaseModel | None  # populated when schema was supplied in the request
    model: str  # model identifier the adapter used
    adapter_id: str  # one of VALID_ADAPTER_IDS or "in-memory" for the stub
    usage: LLMUsage
    latency_ms: int


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system: str | None = None
    schema: type[BaseModel] | None = None
    temperature: float = 0.0
    max_output_tokens: int | None = None
    stop: list[str] | None = None
    model_hint: str | None = None  # "extraction" | "classification" | "summary" | "chat"


# ── Protocol ──────────────────────────────────────────────────────────────────


class LLMProvider(Protocol):
    id: str
    version: str

    async def complete(
        self,
        ctx: TenantContext,
        request: LLMRequest,
    ) -> LLMResponse:
        """Call the LLM and return a structured response.

        Raises:
            LLMUnavailable: network or service failure.
            LLMRateLimited: quota exceeded.
            LLMAuthenticationFailed: invalid or expired credentials.
            LLMSchemaViolation: structured output did not match the schema.
            LLMContextWindowExceeded: prompt exceeds model context limit.
            LLMContentFiltered: provider content policy blocked the request.
            LLMInvalidRequest: malformed request (400).
        """
        ...
