# iris-adapter-llm-azure-openai

Azure OpenAI LLM adapter for IRIS. Calls Azure-hosted OpenAI models via the Azure OpenAI Service REST API.

## Requirements

- An Azure subscription with an Azure OpenAI resource
- At least one model deployment (chat and optionally a separate extraction deployment)
- Python 3.12+

## Installation

This package is a workspace member and is installed automatically by `uv sync --all-packages`. To install standalone:

```bash
uv add iris-adapter-llm-azure-openai
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `IRIS_LLM_AZURE_RESOURCE` | Yes | - | Azure resource name (subdomain of `openai.azure.com`) |
| `IRIS_LLM_AZURE_API_KEY` | Yes | - | Azure OpenAI API key |
| `IRIS_LLM_AZURE_DEPLOYMENT_CHAT` | Yes | - | Deployment name for chat and general completion |
| `IRIS_LLM_AZURE_DEPLOYMENT_EXTRACT` | Yes | - | Deployment name for structured extraction requests |
| `IRIS_LLM_AZURE_API_VERSION` | No | `2024-02-01` | Azure OpenAI API version |

The endpoint is constructed as:
```
https://{IRIS_LLM_AZURE_RESOURCE}.openai.azure.com/openai/deployments/{deployment}/chat/completions
```

## Model identifiers

Azure OpenAI uses deployment names, not model names. Create deployments in [Azure AI Studio](https://oai.azure.com) and use those deployment names as `IRIS_LLM_AZURE_DEPLOYMENT_CHAT` and `IRIS_LLM_AZURE_DEPLOYMENT_EXTRACT`.

Common deployment models:

| Model | Use case |
|---|---|
| `gpt-4o-mini` | Fast, cheap, general use |
| `gpt-4o` | Higher quality, structured extraction |

Model routing: requests with `model_hint="extraction"` use `IRIS_LLM_AZURE_DEPLOYMENT_EXTRACT`; all others use `IRIS_LLM_AZURE_DEPLOYMENT_CHAT`.

## Usage

```python
from iris_adapter_llm_azure_openai import AzureOpenAIProvider
from iris_engine.contracts.llm_provider import LLMRequest, TenantContext

provider = AzureOpenAIProvider.from_env()
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
from iris_adapter_llm_azure_openai import AzureOpenAIProvider

provider = AzureOpenAIProvider.from_env(
    retry_config=RetryConfig(max_retries=3, backoff_ms=500)
)
```

| Parameter | Default | Description |
|---|---|---|
| `max_retries` | 3 | Maximum retry attempts on 429 or 5xx |
| `backoff_ms` | 500 | Initial backoff in milliseconds (doubles each retry) |

## Live testing

```bash
IRIS_LLM_LIVE_AZURE=1 uv run --env-file .env pytest \
    packages/iris-adapters/llm-azure-openai/tests/test_live.py -v
```

Requires all `IRIS_LLM_AZURE_*` variables to be set.

## Known limitations

- **Deployment names not model names:** The `model` field in `LLMResponse` reflects the deployment name returned by the API, not the underlying model version.
- **C-LLM-009 pre-flight:** Context window overflow on input is not checked before the request. The API returns a 400 which maps to `LLMInvalidRequest`. Output truncation (`finish_reason: length`) correctly raises `LLMContextWindowExceeded`.
- **API version pinning:** The default API version (`2024-02-01`) may not support all features of newer deployments. Set `IRIS_LLM_AZURE_API_VERSION` to match your deployment's supported versions (e.g. `2025-01-01-preview`).
- **No streaming:** `complete()` waits for the full response. Streaming is not supported.
