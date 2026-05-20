# Contract: LLMProvider

This contract defines the Protocol every LLM adapter implements. The contract test suite (workstream task T047) verifies each adapter against every clause below.

## Types

```python
from typing import Protocol, Optional, Type, TypeVar
from dataclasses import dataclass
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int            # must equal input + output

@dataclass(frozen=True)
class LLMResponse:
    text: str
    structured: Optional[BaseModel]   # populated when a schema was supplied
    model: str                        # model identifier the adapter actually used
    adapter_id: str                   # "azure-openai" | "openai" | "anthropic" | "local"
    usage: LLMUsage
    latency_ms: int

@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system: Optional[str] = None
    schema: Optional[Type[BaseModel]] = None
    temperature: float = 0.0
    max_output_tokens: Optional[int] = None
    stop: Optional[list[str]] = None
    model_hint: Optional[str] = None  # "extraction" | "classification" | "summary" | "chat"

class LLMProvider(Protocol):
    id: str
    version: str

    async def complete(
        self,
        ctx: TenantContext,
        request: LLMRequest,
    ) -> LLMResponse: ...
```

## Errors

```python
class LLMError(Exception): ...
class LLMUnavailable(LLMError): ...                  # 5xx, network failure, timeout
class LLMRateLimited(LLMError): ...                  # 429, quota exhausted
class LLMAuthenticationFailed(LLMError): ...         # 401, 403, invalid key
class LLMSchemaViolation(LLMError): ...              # structured output did not match the schema
class LLMContextWindowExceeded(LLMError): ...        # prompt + max_output_tokens > model limit
class LLMContentFiltered(LLMError): ...              # provider content policy blocked the call
class LLMInvalidRequest(LLMError): ...               # 400 from the provider
```

## Contract clauses

### C-LLM-001 Adapter exposes a stable identifier

The `id` attribute matches one of `azure-openai`, `openai`, `anthropic`, `local`. The `version` attribute is semver.

### C-LLM-002 Text round-trip

Given `LLMRequest(prompt="Reply with the single word OK")`, `complete` returns an `LLMResponse` whose `text` contains the substring `OK` (case-insensitive).

### C-LLM-003 Token usage math

`response.usage.total_tokens == response.usage.input_tokens + response.usage.output_tokens`.

### C-LLM-004 Non-zero token counts on non-empty completion

Given a non-empty prompt and a non-empty response, both `input_tokens` and `output_tokens` are greater than zero.

### C-LLM-005 Structured output is validated

Given a Pydantic schema and a prompt that elicits a populated structured response, `response.structured` is a non-None instance of the schema, and `isinstance(response.structured, schema)` is true.

### C-LLM-006 Structured output failure is typed

Given a schema with a required field and a prompt that does not elicit the field, the adapter raises `LLMSchemaViolation`.

### C-LLM-007 Authentication failure is typed

An adapter configured with an obviously invalid API key (`sk-invalid`) raises `LLMAuthenticationFailed` on the first call. The error message contains the adapter id; it does not contain the API key.

### C-LLM-008 Rate limit is typed and retryable

A mock provider returning `429` once and then `200` returns a valid `LLMResponse` after one retry. The retry count is observable via the OTEL span.

### C-LLM-009 Context window exceeded is typed

A request whose `prompt` plus `max_output_tokens` exceeds the model's window raises `LLMContextWindowExceeded`. The error message includes the requested total and the model's limit.

### C-LLM-010 Adapter identifier appears in response

`response.adapter_id == adapter.id`.

### C-LLM-011 Tenant context is preserved in telemetry

The OTEL span emitted by `complete` carries `tenant_id`, `adapter_id`, `model`, `input_tokens`, `output_tokens`, `latency_ms`, and the boolean `structured_output_used`.

### C-LLM-LOCAL-001 No outbound network access

The local adapter (pointed at `http://localhost:8080/v1`) returns a valid `LLMResponse` with all sockets except `localhost` blocked.

### C-LLM-LIVE-001 Round-trip against the real endpoint

`IRIS_LLM_LIVE_<ADAPTER>=1` enables a single live completion against the adapter's real endpoint. The result matches every applicable unit clause.
