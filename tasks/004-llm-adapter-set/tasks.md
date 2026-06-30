# Tasks 004: LLM Adapter Set

**Workstream**: `004-llm-adapter-set`
**Spec**: [spec.md](./spec.md)  -  **Plan**: [plan.md](./plan.md)  -  **Contract**: [contracts/llm-provider.md](./contracts/llm-provider.md)
**Markers**: `[P]` parallelisable, `[US#]` user-story tag, `[size: S|M|L]`, `[owner: AuroPro]`.

## Sprint 1: Protocol + selector

- [x] **T040** `[US2] [US8] [size: S] [owner: AuroPro]` Add `iris_engine/contracts/llm_provider.py` with the Protocol, `LLMRequest`, `LLMResponse`, `LLMUsage`, and the error types from the contract document.
      **Acceptance**: mypy strict passes; the module imports with zero adapter dependencies.

- [x] **T041** `[P] [US1] [size: M] [owner: AuroPro]` Implement `iris_engine/llm/selector.py`. Reads `ProductConfig.adapters.llm`, returns the configured `LLMProvider`. Optional fallback path.
      **Acceptance**: Unit tests cover primary success, primary-`LLMUnavailable`-falls-back-to-secondary, and both-fail-surfaces-primary-error.

- [x] **T042** `[P] [US9] [size: M] [owner: AuroPro]` Implement `iris_engine/llm/in_memory.py` with `StubLLMProvider` returning canned responses including a populated `structured` field when a schema is supplied. Used by every agent test in workstream 005.
      **Acceptance**: The stub passes every contract clause where it makes sense (skips live-only clauses).

## Sprint 1: Shared base

- [x] **T043** `[US2] [size: M] [owner: AuroPro]` Create `packages/iris-adapters/llm-shared/` with the OpenAI-compatible HTTP base class and a retry helper. Not a published package; consumed only by `llm-azure-openai`, `llm-openai`, and `llm-local`.
      **Acceptance**: A subclass that points at a mock server passes the OpenAI-compatible contract clauses with zero per-subclass code.

## Sprint 1: Adapter packages (parallel)

- [x] **T044** `[P] [US1] [US3] [US5] [US6] [size: L] [owner: AuroPro]` `packages/iris-adapters/llm-azure-openai/`. Inherits from the OpenAI-compatible base. Adds Azure-specific endpoint URL construction (`{resource}.openai.azure.com/openai/deployments/{deployment}/chat/completions`), API-version query param, and `api-key` header.
      **Acceptance**: Unit tests with mocked Azure responses pass every contract clause; live clause runs under `IRIS_LLM_LIVE_AZURE=1`.

- [x] **T045** `[P] [US1] [US3] [US5] [US6] [size: M] [owner: AuroPro]` `packages/iris-adapters/llm-openai/`. Inherits from the OpenAI-compatible base. Standard `api.openai.com/v1` endpoint and `Authorization: Bearer` header.
      **Acceptance**: Unit tests pass; live clause runs under `IRIS_LLM_LIVE_OPENAI=1`.

- [x] **T046** `[P] [US1] [US3] [US5] [US6] [size: L] [owner: AuroPro]` `packages/iris-adapters/llm-anthropic/`. Standalone implementation against the Anthropic messages API. Structured output via tool use. Token counting from the response headers / fields.
      **Acceptance**: Unit tests pass; live clause runs under `IRIS_LLM_LIVE_ANTHROPIC=1`; tool-use structured output clause C-LLM-005 passes.

- [x] **T047** `[P] [US1] [US4] [size: M] [owner: AuroPro]` `packages/iris-adapters/llm-local/`. Inherits from the OpenAI-compatible base. Targets a local vLLM or Ollama endpoint declared via `IRIS_LLM_LOCAL_URL` (default `http://localhost:8080/v1`).
      **Acceptance**: Unit tests pass; the airgapped clause C-LLM-LOCAL-001 passes; integration test against a real Ollama running in CI optional.

## Sprint 1: Contract suite + telemetry

- [ ] **T048** `[US9] [size: M] [owner: AuroPro]` `tests/contract/test_llm_contract.py`: parametrised contract suite over every registered adapter.
      **Acceptance**: All clauses C-LLM-001 through C-LLM-011 pass for every registered adapter under `make test`.

- [ ] **T049** `[P] [US11] [size: S] [owner: AuroPro]` Add an OTEL span wrapper to every adapter's `complete`. Records the attributes listed in clause C-LLM-011.
      **Acceptance**: Integration test verifies the span attributes on each adapter.

## Sprint 1: Documentation

- [ ] **T050** `[P] [size: S] [owner: AuroPro]` Per-adapter README under `packages/iris-adapters/llm-<name>/README.md` covering env vars, model identifiers, retry tuning, and known limitations.
      **Acceptance**: A team member can install and exercise any adapter from the README alone.

## Definition of Done

1. All four adapters pass the contract suite under `make test`.
2. `make test` finishes without contacting any external LLM endpoint.
3. `IRIS_LLM_LIVE_<NAME>=1 make test` exercises the named adapter against its real endpoint.
4. A Product with `adapters.llm: anthropic` routes agent calls through the Anthropic adapter (verified by adapter telemetry).
5. Structured output (Pydantic schema) round-trips through every adapter.
