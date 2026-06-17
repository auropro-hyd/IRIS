"""Unit tests for iris_engine.llm.selector (T041) and StubLLMProvider (T042)."""

from __future__ import annotations

import asyncio

import pytest
from iris_engine.contracts.llm_provider import (
    LLMRequest,
    LLMResponse,
    LLMSchemaViolation,
    LLMUnavailable,
    LLMUsage,
    TenantContext,
)
from iris_engine.llm.in_memory import StubLLMProvider
from iris_engine.llm.selector import select_llm_provider
from iris_engine.llm.tracing import instrument_complete
from pydantic import BaseModel

_CTX = TenantContext(tenant_id="test-tenant", product_slug="auto/in")
_REQ = LLMRequest(prompt="Reply with the single word OK")


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


# ── helpers ───────────────────────────────────────────────────────────────────


class _UnavailableProvider:
    """Always raises LLMUnavailable - simulates a failed primary adapter."""

    version = "1.0.0"

    def __init__(self, adapter_id: str = "failing", message: str = "service down") -> None:
        self.id = adapter_id
        self._message = message

    async def complete(self, ctx: TenantContext, request: LLMRequest) -> LLMResponse:
        raise LLMUnavailable(self._message)


class _ExtractionResult(BaseModel):
    field: str


# ── T041: selector ────────────────────────────────────────────────────────────


def test_select_returns_primary_provider() -> None:
    stub = StubLLMProvider(adapter_id="anthropic")
    registry = {"anthropic": stub}
    selected = select_llm_provider(registry, "anthropic")
    assert selected is stub


def test_select_no_fallback_returns_provider_directly() -> None:
    stub = StubLLMProvider(adapter_id="openai")
    registry = {"openai": stub}
    selected = select_llm_provider(registry, "openai")
    result = _run(selected.complete(_CTX, _REQ))
    assert result.adapter_id == "openai"


def test_select_unknown_adapter_raises_key_error() -> None:
    with pytest.raises(KeyError, match="anthropic"):
        select_llm_provider({}, "anthropic")


def test_select_unknown_fallback_raises_key_error() -> None:
    stub = StubLLMProvider(adapter_id="openai")
    with pytest.raises(KeyError, match="anthropic"):
        select_llm_provider({"openai": stub}, "openai", fallback_id="anthropic")


def test_select_primary_success_fallback_not_called() -> None:
    primary = StubLLMProvider(adapter_id="azure-openai", default_text="from-primary")
    fallback = StubLLMProvider(adapter_id="anthropic", default_text="from-fallback")
    registry = {"azure-openai": primary, "anthropic": fallback}
    provider = select_llm_provider(registry, "azure-openai", fallback_id="anthropic")
    result = _run(provider.complete(_CTX, _REQ))
    assert result.text == "from-primary"


def test_select_primary_unavailable_fallback_succeeds() -> None:
    primary = _UnavailableProvider(adapter_id="azure-openai")
    fallback = StubLLMProvider(adapter_id="anthropic")
    registry = {"azure-openai": primary, "anthropic": fallback}
    provider = select_llm_provider(registry, "azure-openai", fallback_id="anthropic")
    result = _run(provider.complete(_CTX, _REQ))
    assert result.adapter_id == "anthropic"


def test_select_primary_and_fallback_both_fail_surfaces_primary_error() -> None:
    primary = _UnavailableProvider(adapter_id="azure-openai", message="primary down")
    fallback = _UnavailableProvider(adapter_id="anthropic", message="fallback down")
    registry = {"azure-openai": primary, "anthropic": fallback}
    provider = select_llm_provider(registry, "azure-openai", fallback_id="anthropic")
    with pytest.raises(LLMUnavailable, match="primary down"):
        _run(provider.complete(_CTX, _REQ))


def test_select_with_fallback_exposes_primary_id() -> None:
    primary = StubLLMProvider(adapter_id="azure-openai")
    fallback = StubLLMProvider(adapter_id="anthropic")
    registry = {"azure-openai": primary, "anthropic": fallback}
    provider = select_llm_provider(registry, "azure-openai", fallback_id="anthropic")
    assert provider.id == "azure-openai"


# ── T042: StubLLMProvider ─────────────────────────────────────────────────────


def test_stub_returns_llm_response() -> None:
    stub = StubLLMProvider()
    result = _run(stub.complete(_CTX, _REQ))
    assert isinstance(result, LLMResponse)


def test_stub_default_text_contains_ok() -> None:
    stub = StubLLMProvider()
    result = _run(stub.complete(_CTX, _REQ))
    assert "ok" in result.text.lower()


def test_stub_default_adapter_id_is_in_memory() -> None:
    stub = StubLLMProvider()
    assert stub.id == "in-memory"


def test_stub_custom_adapter_id_is_reflected_in_response() -> None:
    stub = StubLLMProvider(adapter_id="azure-openai")
    result = _run(stub.complete(_CTX, _REQ))
    assert result.adapter_id == "azure-openai"


def test_stub_version_is_semver() -> None:
    stub = StubLLMProvider()
    parts = stub.version.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts)


def test_stub_usage_math_is_correct() -> None:
    stub = StubLLMProvider()
    result = _run(stub.complete(_CTX, _REQ))
    assert result.usage.total_tokens == result.usage.input_tokens + result.usage.output_tokens


def test_stub_usage_counts_are_nonzero() -> None:
    stub = StubLLMProvider()
    result = _run(stub.complete(_CTX, _REQ))
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0


def test_stub_custom_usage_is_returned() -> None:
    usage = LLMUsage(input_tokens=100, output_tokens=50, total_tokens=150)
    stub = StubLLMProvider(default_usage=usage)
    result = _run(stub.complete(_CTX, _REQ))
    assert result.usage is usage


def test_stub_no_schema_returns_none_structured() -> None:
    stub = StubLLMProvider()
    result = _run(stub.complete(_CTX, _REQ))
    assert result.structured is None


def test_stub_registered_schema_returns_validated_instance() -> None:
    instance = _ExtractionResult(field="value")
    stub = StubLLMProvider(structured_instances={_ExtractionResult: instance})
    req = LLMRequest(prompt="extract", schema=_ExtractionResult)
    result = _run(stub.complete(_CTX, req))
    assert isinstance(result.structured, _ExtractionResult)
    assert result.structured is instance


def test_stub_unregistered_schema_raises_schema_violation() -> None:
    stub = StubLLMProvider()
    req = LLMRequest(prompt="extract", schema=_ExtractionResult)
    with pytest.raises(LLMSchemaViolation):
        _run(stub.complete(_CTX, req))


def test_stub_raise_on_complete_raises_configured_error() -> None:
    error = LLMUnavailable("service down")
    stub = StubLLMProvider(raise_on_complete=error)
    with pytest.raises(LLMUnavailable, match="service down"):
        _run(stub.complete(_CTX, _REQ))


# ── tracing coverage: generic exception path ─────────────────────────────────
# OTEL span *attribute* verification is in the contract suite (T048/T049).
# This test only confirms the generic-exception branch in tracing.py re-raises.


def test_tracing_generic_exception_is_reraised() -> None:
    async def _exercise() -> None:
        async with instrument_complete("test-adapter", _CTX, _REQ):
            raise RuntimeError("not an LLM error")

    with pytest.raises(RuntimeError, match="not an LLM error"):
        _run(_exercise())
