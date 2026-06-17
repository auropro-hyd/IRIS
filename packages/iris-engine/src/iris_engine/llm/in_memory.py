"""StubLLMProvider: in-memory fake for tests and local development.

Returns canned LLMResponse values when pre-registered, or a minimal default
otherwise. Raises the correct typed errors for schema mismatches and injected
error conditions so it satisfies the LLMProvider contract without contacting
any real service.
"""

from __future__ import annotations

from pydantic import BaseModel

from iris_engine.contracts.llm_provider import (
    LLMError,
    LLMRequest,
    LLMResponse,
    LLMSchemaViolation,
    LLMUsage,
    TenantContext,
)

_DEFAULT_USAGE = LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15)


class StubLLMProvider:
    """In-memory LLM provider that returns pre-set or default LLMResponse values."""

    version: str = "1.0.0"

    def __init__(
        self,
        default_text: str = "OK",
        default_model: str = "stub-model",
        default_usage: LLMUsage | None = None,
        structured_instances: dict[type[BaseModel], BaseModel] | None = None,
        raise_on_complete: LLMError | None = None,
        adapter_id: str = "in-memory",
    ) -> None:
        self.id = adapter_id
        self._default_text = default_text
        self._default_model = default_model
        self._default_usage = default_usage or _DEFAULT_USAGE
        self._structured_instances: dict[type[BaseModel], BaseModel] = structured_instances or {}
        self._raise_on_complete = raise_on_complete

    async def complete(
        self,
        ctx: TenantContext,
        request: LLMRequest,
    ) -> LLMResponse:
        from iris_engine.llm.tracing import instrument_complete, log_complete_success

        async with instrument_complete(self.id, ctx, request) as span:
            if self._raise_on_complete is not None:
                raise self._raise_on_complete

            structured: BaseModel | None = None
            if request.schema is not None:
                if request.schema in self._structured_instances:
                    structured = self._structured_instances[request.schema]
                else:
                    raise LLMSchemaViolation(
                        f"[{self.id}] no registered structured instance for"
                        f" {request.schema.__name__}"
                    )

            result = LLMResponse(
                text=self._default_text,
                structured=structured,
                model=self._default_model,
                adapter_id=self.id,
                usage=self._default_usage,
                latency_ms=0,
            )

            span.set_attribute("llm.model", result.model)
            span.set_attribute("llm.input_tokens", result.usage.input_tokens)
            span.set_attribute("llm.output_tokens", result.usage.output_tokens)
            span.set_attribute("llm.latency_ms", result.latency_ms)
            span.set_attribute("llm.structured_output_used", result.structured is not None)

            log_complete_success(self.id, ctx, result)
            return result
