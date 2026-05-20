# Plan 004: LLM Adapter Set

**Workstream**: `004-llm-adapter-set`
**Status**: Draft
**Specification**: [spec.md](./spec.md)  -  **Contract**: [contracts/llm-provider.md](./contracts/llm-provider.md)

## Approach

The `LLMProvider` Protocol lives in `iris-engine`. The four adapters are independent packages. A selector in `iris-engine` reads `ProductConfig.adapters.llm` and returns the configured `LLMProvider` instance.

OpenAI, Azure OpenAI, and the local vLLM / Ollama adapter all speak an OpenAI-compatible HTTP shape; they share a base class. Anthropic is sufficiently different (messages API, tool-use schema for structured output) to warrant a standalone implementation.

This workstream lands the Protocol and the adapters. The Model Gateway proper (region pinning, PII redaction, daily caps, cost ledger) is a later workstream that wraps any `LLMProvider`; the adapters in this workstream are gateway-ready by virtue of returning `LLMUsage` on every response.

## Proposed file layout

```
packages/iris-engine/src/iris_engine/contracts/
└── llm_provider.py            # LLMProvider Protocol + LLMRequest / LLMResponse / errors

packages/iris-engine/src/iris_engine/llm/
├── __init__.py                # LLMProvider, select_llm_provider()
├── selector.py                # reads adapters.llm from ProductConfig
└── in_memory.py               # StubLLMProvider for tests

packages/iris-adapters/llm-azure-openai/
├── pyproject.toml
└── src/iris_adapter_llm_azure_openai/
    ├── __init__.py            # AzureOpenAIProvider
    ├── client.py              # async client wiring
    └── structured.py          # JSON-mode handling

packages/iris-adapters/llm-openai/
├── pyproject.toml
└── src/iris_adapter_llm_openai/
    └── __init__.py            # OpenAIProvider (shares base with azure-openai)

packages/iris-adapters/llm-anthropic/
├── pyproject.toml
└── src/iris_adapter_llm_anthropic/
    ├── __init__.py            # AnthropicProvider
    └── structured.py          # tool-use-based structured output

packages/iris-adapters/llm-local/
├── pyproject.toml             # works against vLLM or Ollama (both expose OpenAI-compatible HTTP)
└── src/iris_adapter_llm_local/
    └── __init__.py            # LocalLLMProvider

packages/iris-adapters/llm-shared/        # internal package, not published
├── pyproject.toml
└── src/iris_adapter_llm_shared/
    ├── openai_compat.py       # shared base for openai-shape providers
    └── retry.py               # shared retry helper

tests/contract/
└── test_llm_contract.py       # parametrised over registered adapters
```

## Key choices

1. **Shared OpenAI-compatible base class** under `llm-shared/`. Azure OpenAI, OpenAI direct, and the local adapter inherit; Anthropic stands alone.
2. **Structured output via JSON-mode** for OpenAI / Azure, **via tool use** for Anthropic. The adapter abstracts this difference; agents only see "give me a `T`".
3. **Retry is in the adapter**, not in the selector, because retry counts and backoffs differ per provider. The selector adds an outer retry for `LLMUnavailable` only when the Product config specifies a fallback adapter (same pattern as OCR).
4. **Local adapter targets the OpenAI-compatible HTTP**. Both vLLM and Ollama expose that shape, so one adapter handles both.
5. **Embeddings are out of scope for this workstream**. Each adapter exposes only `complete`. The embedding path lands with the Knowledge Store workstream.
6. **No streaming yet**. The contract is request-response. Streaming lands when the workbench needs it; the Protocol will gain an optional `stream` method then.

## Configuration shape (consumed from workstream 002)

```yaml
# config/products/commercial-auto-claims/in/product.yaml
adapters:
  llm: azure-openai              # one of: azure-openai | openai | anthropic | local
  llm_fallback: anthropic        # optional
  llm_params:
    model_chat: gpt-4o-mini          # adapter-specific model identifier
    model_extract: gpt-4o-mini
    max_retries: 3
    retry_backoff_ms: 500
```

## Out of scope

- Model Gateway proper (separate workstream, lands later).
- Vision / multimodal calls.
- Streaming responses.
- Function calling beyond schema-driven structured output.
- Embeddings (covered by the Knowledge Store workstream).

## Dependencies

- Workstream 001 (scaffold).
- Workstream 002 (configuration framework) for the adapter selection.
