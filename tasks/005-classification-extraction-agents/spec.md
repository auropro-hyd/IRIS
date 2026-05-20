# Specification 005: Classification and Extraction Agents

**Workstream**: `005-classification-extraction-agents`
**Status**: Draft
**Architect**: Anmol Jaiswal
**Input**: Direction to build the core services for OCR ingestion plus classification and extraction capabilities, sitting on top of the swappable OCR and LLM adapters.

## Background

The PoCs already have working classifier and extractor agents. They are duplicated across the two repositories (`backend/agents/document_classifier.py` is byte-for-byte identical in both) and call Azure OpenAI directly. This workstream produces canonical implementations in `iris-agents`, takes their configuration (taxonomy, field set, prompts) from the workstream 002 Product bundle, and runs them through the workstream 003 OCR and workstream 004 LLM adapters.

The result is one classifier and one extractor that work for any Product, against any OCR adapter, and against any LLM adapter, with zero per-tenant code.

## Goals

1. A `DocumentClassifier` agent that takes an `OCRResult` and a Product config and returns a typed classification (document type, confidence, missing-document analysis).
2. A `FieldExtractor` agent that takes an `OCRResult`, a Product config, and a classified document, and returns a typed extraction (FNOL fields, confidences, validation errors).
3. Both agents consume `LLMProvider` via dependency injection.
4. Both agents are unit-tested against the `StubLLMProvider` (no live LLM calls).
5. A "golden set" suite that runs each agent against fixture documents (covering the PoC's test set) and compares against expected outputs.

## Non-goals

- Summarisation. The PoC's summary agent will follow in a separate task once the classifier and extractor are stable.
- Fraud scoring. Later workstream.
- Multi-document reasoning (e.g., comparing two extracted FNOLs). The agents in this workstream operate one document at a time.
- Streaming partial results to the workbench. The agent returns a complete result.

## User Scenarios and Testing

### User Story 1: A FNOL document is classified (Priority: P1)

A user submits a one-page FNOL PDF under the `commercial-auto-claims/in` Product. The classifier identifies it as `fnol_form`, returns a confidence of at least 0.85 against the bundled fixture, and reports zero missing documents (FNOL is self-contained).

**Acceptance Scenario**:
- The agent returns a `Classification` with `document_type == "fnol_form"`.
- `confidence >= 0.85` against the bundled FNOL fixture.
- The classification cites the page and bounding boxes used to make the decision.

### User Story 2: A document not in the taxonomy is rejected (Priority: P1)

A user submits a PDF that does not match any declared document type. The classifier returns `document_type == "unknown"` with a confidence and a reason string.

**Acceptance Scenario**:
- An out-of-taxonomy document fixture (e.g., a recipe) returns `document_type == "unknown"`.
- The result includes a non-empty `reason` field.

### User Story 3: Fields are extracted from a classified document (Priority: P1)

A FNOL document classified in story 1 is passed to the extractor with the same Product config. The extractor returns all required FNOL fields populated; optional fields populated where present; one validation error for the field where the source PDF has an obvious format violation.

**Acceptance Scenario**:
- Every required FNOL field declared in the Product's extraction schema appears in the result with a non-null value.
- A deliberately-broken field in the fixture (e.g., a date in `dd-mm-yyyy` against an `iso-8601` validator) produces a typed `FieldValidationError`.

### User Story 4: The agent runs against any LLM adapter (Priority: P1)

Run the classifier under a Product configured with `adapters.llm: anthropic`, then under one configured with `adapters.llm: azure-openai`. Both produce a valid `Classification` with the same shape.

**Acceptance Scenario**:
- Two integration tests, one per LLM adapter, both produce a populated `Classification`.

### User Story 5: The agent runs against any OCR adapter (Priority: P1)

The same document submitted under Products configured for different OCR adapters produces a valid `Classification` and `Extraction` in each case.

**Acceptance Scenario**:
- The integration test matrix covers two OCR adapters x two LLM adapters and produces a populated result in every cell.

### User Story 6: Prompts come from the Product bundle (Priority: P1)

A Product bundle's `prompts/classify.j2` is the source of truth for the classifier's prompt. Changing the template changes the prompt sent to the LLM with no code change.

**Acceptance Scenario**:
- Editing `prompts/classify.j2` and rerunning the agent produces an LLM call carrying the updated prompt.

### User Story 7: A golden set guards regression (Priority: P2)

A set of fixture documents with expected classifications and extractions runs on every CI build. Any regression in classification accuracy or extraction accuracy fails the build.

**Acceptance Scenario**:
- `make test-golden` runs the golden set; fails the build if classification accuracy drops below the threshold for the Product.
- The threshold is declared in the Product bundle (e.g., `accuracy.classification_min: 0.92`).

### User Story 8: Telemetry covers the agent layer (Priority: P2)

Every agent call emits an OTEL span recording: tenant, Product, agent identifier, document identifier, LLM adapter used, OCR adapter used, total latency, LLM token usage, and outcome (success, validation error, LLM error).

**Acceptance Scenario**:
- A successful classifier run produces a span with all listed attributes.
- A run that fails on validation produces a span with `outcome=validation_error` and the field names that failed.

## Out of scope

- Summarisation. Follow-up task.
- Multi-document reasoning.
- Streaming partial output.
- Per-tenant fine-tuning. Tenants get the Product's prompts and validators; tuning a model is a later workstream.
