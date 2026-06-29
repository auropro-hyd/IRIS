# iris-adapter-llm-openai

OpenAI LLM adapter for IRIS. Calls the OpenAI Chat Completions API (`api.openai.com/v1`).

## Requirements

- An OpenAI API key with access to the models you want to use
- Python 3.12+

## Installation

This package is a workspace member and is installed automatically by `uv sync --all-packages`. To install standalone:

```bash
uv add iris-adapter-llm-openai
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `IRIS_LLM_OPENAI_API_KEY` | Yes | - | OpenAI API key (`sk-...`) |
| `IRIS_LLM_OPENAI_MODEL_CHAT` | No | `gpt-4o-mini` | Model for chat and general completion |
| `IRIS_LLM_OPENAI_MODEL_EXTRACT` | No | `gpt-4o-mini` | Model for structured extraction requests |

## Model identifiers

Any model available on your OpenAI account. Common choices:

| Model | Use case |
|---|---|
| `gpt-4o-mini` | Fast, cheap, general use |
| `gpt-4o` | Higher quality, structured extraction |
| `gpt-4-turbo` | Large context window |

Model routing: requests with `model_hint="extraction"` use `IRIS_LLM_OPENAI_MODEL_EXTRACT`; all others use `IRIS_LLM_OPENAI_MODEL_CHAT`.

## Usage

```python
from iris_adapter_llm_openai import OpenAIProvider
from iris_engine.contracts.llm_provider import LLMRequest, TenantContext

provider = OpenAIProvider.from_env()
ctx = TenantContext(tenant_id="my-tenant", product_slug="my/product")
req = LLMRequest(prompt="Summarise this document in one sentence.")

import asyncio
result = asyncio.run(provider.complete(ctx, req))
print(result.text)
print(f"tokens: {result.usage.input_tokens} in / {result.usage.output_tokens} out")
```

### Structured output

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
from iris_adapter_llm_openai import OpenAIProvider

provider = OpenAIProvider.from_env(
    retry_config=RetryConfig(max_retries=3, backoff_ms=500)
)
```

| Parameter | Default | Description |
|---|---|---|
| `max_retries` | 3 | Maximum retry attempts on 429 or 5xx |
| `backoff_ms` | 500 | Initial backoff in milliseconds (doubles each retry) |

## Live testing

```bash
IRIS_LLM_LIVE_OPENAI=1 uv run --env-file .env pytest \
    packages/iris-adapters/llm-openai/tests/test_live.py -v
```

Requires `IRIS_LLM_OPENAI_API_KEY` to be set.

## Known limitations

- **C-LLM-009 pre-flight:** Context window overflow on input is not checked before the request. The API returns a 400 which maps to `LLMInvalidRequest`. Output truncation (`finish_reason: length`) correctly raises `LLMContextWindowExceeded`.
- **No streaming:** `complete()` waits for the full response. Streaming is not supported.
