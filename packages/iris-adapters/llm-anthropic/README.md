# iris-adapter-llm-anthropic

Anthropic LLM adapter for IRIS. Calls the Anthropic Messages API (`api.anthropic.com/v1/messages`) directly - does not go through an OpenAI-compatibility layer.

## Requirements

- An Anthropic API key
- Python 3.12+

## Installation

This package is a workspace member and is installed automatically by `uv sync --all-packages`. To install standalone:

```bash
uv add iris-adapter-llm-anthropic
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `IRIS_LLM_ANTHROPIC_API_KEY` | Yes | - | Anthropic API key (`sk-ant-...`); sent as `x-api-key` header alongside `anthropic-version: 2023-06-01` |
| `IRIS_LLM_ANTHROPIC_MODEL_CHAT` | No | `claude-haiku-4-5-20251001` | Model for chat and general completion |
| `IRIS_LLM_ANTHROPIC_MODEL_EXTRACT` | No | `claude-haiku-4-5-20251001` | Model for structured extraction requests |

## Model identifiers

| Model | Use case |
|---|---|
| `claude-haiku-4-5-20251001` | Fast, cheap, general use |
| `claude-sonnet-4-6` | Higher quality, balanced cost |
| `claude-opus-4-8` | Highest quality, complex reasoning |

Model routing: requests with `model_hint="extraction"` use `IRIS_LLM_ANTHROPIC_MODEL_EXTRACT`; all others use `IRIS_LLM_ANTHROPIC_MODEL_CHAT`.

## Usage

```python
from iris_adapter_llm_anthropic import AnthropicProvider
from iris_engine.contracts.llm_provider import LLMRequest, TenantContext

provider = AnthropicProvider.from_env()
ctx = TenantContext(tenant_id="my-tenant", product_slug="my/product")
req = LLMRequest(prompt="Summarise this document in one sentence.")

import asyncio
result = asyncio.run(provider.complete(ctx, req))
print(result.text)
print(f"tokens: {result.usage.input_tokens} in / {result.usage.output_tokens} out")
```

### Structured output

Anthropic structured output uses the tool-use pattern, not JSON mode. The adapter handles this automatically:

```python
from pydantic import BaseModel

class Invoice(BaseModel):
    vendor: str
    total: float

req = LLMRequest(
    prompt="Extract the vendor and total from this invoice text: ...",
    schema=Invoice,
    model_hint="extraction",
)
result = asyncio.run(provider.complete(ctx, req))
print(result.structured)  # Invoice(vendor=..., total=...)
```

## Retry tuning

```python
from iris_adapter_llm_shared.retry import RetryConfig
from iris_adapter_llm_anthropic import AnthropicProvider

provider = AnthropicProvider.from_env(
    retry_config=RetryConfig(max_retries=3, backoff_ms=500)
)
```

| Parameter | Default | Description |
|---|---|---|
| `max_retries` | 3 | Maximum retry attempts on 429 or 5xx |
| `backoff_ms` | 500 | Initial backoff in milliseconds (doubles each retry) |

## Live testing

```bash
IRIS_LLM_LIVE_ANTHROPIC=1 uv run --env-file .env pytest \
    packages/iris-adapters/llm-anthropic/tests/test_live.py -v
```

Requires `IRIS_LLM_ANTHROPIC_API_KEY` to be set.

## Known limitations

- **Structured output via tool use:** Unlike OpenAI JSON mode, Anthropic structured output works by defining a tool and forcing the model to call it. This is handled internally - the caller just passes a Pydantic `schema` in `LLMRequest`.
- **`stop_reason: max_tokens`:** Means the output budget was exhausted, not that the context window was exceeded. Raises `LLMContextWindowExceeded` as the closest semantic match.
- **C-LLM-009 pre-flight:** Input-token pre-flight check is not implemented. HTTP 400 from the API maps to `LLMInvalidRequest`.
- **No streaming:** `complete()` waits for the full response. Streaming is not supported.
