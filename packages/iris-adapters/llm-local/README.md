# iris-adapter-llm-local

Local LLM adapter for IRIS. Targets any OpenAI-compatible inference server running on your own hardware or private network: [Ollama](https://ollama.com), [vLLM](https://github.com/vllm-project/vllm), [llama.cpp](https://github.com/ggerganov/llama.cpp), and others.

## Requirements

- A running OpenAI-compatible inference server
- The model you want to use already pulled/loaded on that server
- Python 3.12+

## Installation

This package is a workspace member and is installed automatically by `uv sync --all-packages`. To install standalone:

```bash
uv add iris-adapter-llm-local
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `IRIS_LLM_LOCAL_MODEL` | Yes | - | Model name as the server knows it (e.g. `mistral`, `llama3:8b`) |
| `IRIS_LLM_LOCAL_URL` | No | `http://localhost:8080/v1` | Base URL of the inference server |
| `IRIS_LLM_LOCAL_API_KEY` | No | _(empty)_ | Bearer token. Omit for servers that require no auth (Ollama default) |

### Ollama

```bash
IRIS_LLM_LOCAL_MODEL=mistral
IRIS_LLM_LOCAL_URL=http://localhost:11434/v1
```

### vLLM

```bash
IRIS_LLM_LOCAL_MODEL=mistralai/Mistral-7B-Instruct-v0.2
IRIS_LLM_LOCAL_URL=http://localhost:8000/v1
IRIS_LLM_LOCAL_API_KEY=your-vllm-token
```

### llama.cpp server

```bash
IRIS_LLM_LOCAL_MODEL=mistral-7b
IRIS_LLM_LOCAL_URL=http://localhost:8080/v1
```

## Model identifiers

The model name must match exactly what the server expects. Check your server:

```bash
# Ollama - list available models
curl http://localhost:11434/api/tags

# vLLM - list available models
curl http://localhost:8000/v1/models
```

Unlike cloud adapters, there is no chat/extraction model split. The single `IRIS_LLM_LOCAL_MODEL` is used for all request types.

## Usage

```python
from iris_adapter_llm_local import LocalProvider
from iris_engine.contracts.llm_provider import LLMRequest, TenantContext

provider = LocalProvider.from_env()
ctx = TenantContext(tenant_id="my-tenant", product_slug="my/product")
req = LLMRequest(prompt="Summarise this document in one sentence.")

import asyncio
result = asyncio.run(provider.complete(ctx, req))
print(result.text)
print(f"tokens: {result.usage.input_tokens} in / {result.usage.output_tokens} out")
```

## Retry tuning

Default retry behaviour is inherited from `OpenAICompatProvider`. Override via `RetryConfig`:

```python
from iris_adapter_llm_shared.retry import RetryConfig
from iris_adapter_llm_local import LocalProvider

provider = LocalProvider.from_env(
    retry_config=RetryConfig(max_retries=3, backoff_ms=500)
)
```

| Parameter | Default | Description |
|---|---|---|
| `max_retries` | 3 | Maximum number of retry attempts on 429 or 5xx |
| `backoff_ms` | 500 | Initial backoff in milliseconds (doubles each retry) |

## Live testing

```bash
IRIS_LLM_LIVE_LOCAL=1 uv run --env-file .env pytest \
    packages/iris-adapters/llm-local/tests/test_live.py -v
```

Requires `IRIS_LLM_LOCAL_MODEL` and a running server at `IRIS_LLM_LOCAL_URL`.

## Known limitations

- **Single model only:** One model per adapter instance. To use different models, create separate `LocalProvider` instances pointing at different servers.
- **No model-hint routing:** The `model_hint` field (`extraction`, `chat`, etc.) is ignored. All requests go to the same model.
- **Structured output:** Uses OpenAI JSON mode (`response_format: {type: "json_object"}`). Not all local servers support this - check your server's documentation.
- **C-LLM-009 pre-flight:** Context window overflow on input is not checked before the request. The server returns a 400 which maps to `LLMInvalidRequest`, not `LLMContextWindowExceeded`. Output truncation (`finish_reason: length`) correctly raises `LLMContextWindowExceeded`.
