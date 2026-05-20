# Specification 004: LLM Adapter Set

**Workstream**: `004-llm-adapter-set`
**Status**: Draft
**Input**: Akhilesh's request: "LLM: Azure, Anthropic, OpenAI and locally / privately hosted LLM models."

## Background

Both PoCs hit Azure OpenAI directly through a helper function. There is no swap path, no provider neutrality, and no place to add cross-cutting policy like region pinning, redaction, or token caps. This workstream introduces an `LLMProvider` Protocol and four adapters, plus a placeholder for the Model Gateway that workstream 005 (and later, the production gateway workstream) will sit on top of.

The four adapters cover:

1. **Azure OpenAI**. Production-grade, regional, paid. The default for India deployments.
2. **Anthropic**. Production-grade, paid. Claude models.
3. **OpenAI direct**. Production-grade, paid. GPT models, used where the tenant is not on Azure.
4. **Local / private**. A self-hosted model served via vLLM or Ollama, talking the OpenAI-compatible HTTP shape.

## Goals

1. One `LLMProvider` Protocol with a stable shape across all four adapters.
2. Four adapter packages, each independently installable.
3. Selection of the active adapter per Product via configuration.
4. A contract test suite that every adapter must pass.
5. A "live" suite that exercises real provider endpoints under environment-variable gates.

## Non-goals

- A full Model Gateway implementation. That is a separate (later) workstream covering region pinning, PII redaction, cost ledger, and daily token caps. This workstream lands the `LLMProvider` contract that the gateway will decorate.
- Vision / multimodal calls. The Protocol shape supports text in, text out, plus structured-output schemas. Image input is a later wave.
- Streaming back to the API client. The adapter contract is request-response; streaming to the workbench will be added when the AG-UI work begins.

## User Scenarios and Testing

### User Story 1: A Product can choose any of the four LLM adapters (Priority: P1)

A Product bundle declares `adapters.llm: anthropic`. Agent calls (classification, extraction) under that Product route through the Anthropic adapter. The same calls under a Product with `adapters.llm: azure-openai` route through Azure OpenAI.

**Acceptance Scenario**:
- Two Products, two LLM selections, two different code paths verified by adapter telemetry.
- The `LLMResponse` type is identical across adapters.

### User Story 2: Adapters return a shared response shape (Priority: P1)

Every adapter returns the same `LLMResponse` type carrying: the text content, the structured output (when a schema is supplied), the model identifier, the token usage (input, output, total), the latency, and the source adapter identifier.

**Acceptance Scenario**:
- Run the contract suite against each adapter; every contract clause passes.
- An agent reads the response without knowing which adapter produced it.

### User Story 3: Structured output is supported uniformly (Priority: P1)

An agent calls `LLMProvider.complete` with a Pydantic schema. The adapter returns an `LLMResponse` whose `structured` field is a validated instance of the schema. The mechanism is JSON-mode for OpenAI / Azure, tool use for Anthropic, and grammar-constrained generation for the local adapter.

**Acceptance Scenario**:
- A schema with required and optional fields is enforced; a missing required field surfaces as an `LLMSchemaViolation`, not a silent default.

### User Story 4: A local model serves traffic with no outbound network (Priority: P1)

A deployment selects `adapters.llm: local`. The adapter calls a local HTTP endpoint (vLLM or Ollama running inside the cluster). No outbound network call is made.

**Acceptance Scenario**:
- A test that blocks outbound traffic at the socket level still produces a valid `LLMResponse` through the local adapter pointed at `http://localhost:8080/v1`.

### User Story 5: Authentication failures are typed (Priority: P1)

An adapter configured with an invalid API key raises `LLMAuthenticationFailed`. The error message does not leak the credential.

**Acceptance Scenario**:
- All four adapters raise `LLMAuthenticationFailed` on an `Invalid API key` 401 response.
- The error message includes the adapter id but does not include the API key.

### User Story 6: Rate limiting is typed and retried (Priority: P1)

An adapter that receives `429` raises `LLMRateLimited`. The selector retries with exponential backoff, up to a per-adapter cap declared in the Product config.

**Acceptance Scenario**:
- A mock provider returning `429` once and then `200` produces a successful `LLMResponse` after one retry.
- A mock provider returning `429` indefinitely raises `LLMRateLimited` after the retry cap is exhausted.

### User Story 7: Live tests are gated (Priority: P2)

Default `pytest` runs do not contact any real LLM endpoint. Setting `IRIS_LLM_LIVE_AZURE=1` (and the corresponding env vars) enables them.

**Acceptance Scenario**:
- `make test` finishes without hitting any external LLM.
- `IRIS_LLM_LIVE_AZURE=1 make test` runs the Azure live suite.

### User Story 8: Token usage is recorded (Priority: P2)

Every `LLMResponse` includes input tokens, output tokens, and total tokens. The orchestrator can read this and write a cost-ledger entry (the cost ledger itself lands later under the Model Gateway workstream).

**Acceptance Scenario**:
- All four adapters return non-zero token counts on a non-empty completion.
- The contract suite verifies the math: `total == input + output`.

### User Story 9: The contract suite catches drift (Priority: P2)

Any change that breaks the shared response shape, or that changes adapter behaviour in an incompatible way, fails the contract suite for that adapter.

## Out of scope

- The Model Gateway proper (region pinning, redaction, cost cap, daily caps).
- Streaming to the API client.
- Function calling beyond the structured-output schema. Tool use as a generic primitive is a later wave.
- Embedding adapters. Embeddings are part of the Knowledge Store workstream (later wave); each LLM adapter exposes a `complete` method only.
