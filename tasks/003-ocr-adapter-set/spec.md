# Specification 003: OCR Adapter Set

**Workstream**: `003-ocr-adapter-set`
**Status**: Draft
**Architect**: Anmol Jaiswal
**Input**: Direction that OCR providers must be swappable. Required adapters: ADI (Azure Document Intelligence), Datalab, PaddleOCR (open-source via Hugging Face), and a locally hosted option.

## Background

Both PoCs call OCR providers directly with no abstraction. Datalab access is wrapped in `backend/infra/ocr/`. There is no path to swap providers without code changes, and there is no path to run a local fallback when network calls fail or are not desired.

This workstream introduces an `OCREngine` Protocol and four adapters that implement it:

1. **ADI** (Azure Document Intelligence). Production-grade, regional, paid.
2. **Datalab**. Production-grade, paid, what the PoCs use today.
3. **PaddleOCR**. Open-source, from Hugging Face, runnable locally.
4. **Local**. Tesseract-based or PaddleOCR running inside the IRIS deployment with no external network call.

The Product configuration framework (workstream 002) selects one adapter per Product. The selection is observable: every OCR call records which adapter ran.

## Goals

1. One `OCREngine` Protocol with a stable shape across all four adapters.
2. Four adapter packages, each independently installable.
3. Selection of the active adapter per Product via configuration.
4. A contract test suite that every adapter must pass.
5. A "live" suite that exercises real provider endpoints, gated by environment variables, so the team can validate against real services without burning credits in normal test runs.

## Non-goals

- Layout-aware extraction (tables, key-value pairs) beyond what each provider returns natively.
- OCR quality benchmarking. Picking an adapter is the Product owner's decision; this workstream provides the choice, not the recommendation.
- A bring-your-own-model adapter. The four named adapters cover the requested surface.

## User Scenarios and Testing

### User Story 1: A Product can choose any of the four OCR adapters (Priority: P1)

A Product bundle declares `adapters.ocr: paddleocr`. Submitting a PDF under that Product routes it through the PaddleOCR adapter. The same PDF submitted under a Product with `adapters.ocr: adi` routes through the Azure Document Intelligence adapter.

**Acceptance Scenario**:
- Two Products, two different OCR selections, two different code paths verified by adapter-level telemetry.
- The OCR result type is identical across adapters.

### User Story 2: Adapters return a shared result shape (Priority: P1)

Every adapter returns the same `OCRResult` type: per-page markdown, per-page bounding boxes for text blocks, the source adapter identifier, and a confidence score per page.

**Acceptance Scenario**:
- Run the contract suite against each adapter; every contract clause passes.
- A consumer (workstream 005 agents) reads the result without knowing which adapter produced it.

### User Story 3: A network failure on a remote adapter does not crash the pipeline (Priority: P1)

The ADI adapter is configured for a Product. The Azure endpoint returns `503`. The adapter raises a typed `OCRUnavailable` error. The orchestrator catches it, marks the document for retry, and (if a fallback is configured in the Product bundle) falls back to the local adapter.

**Acceptance Scenario**:
- A mock ADI server returning `503` does not raise a generic `Exception`; the adapter raises `OCRUnavailable`.
- A Product bundle with `adapters.ocr_fallback: local` does fall back; the document is processed by the local adapter and the event log records the fallback.

### User Story 4: A locally-hosted OCR runs without internet (Priority: P1)

A deployment in an air-gapped environment selects `adapters.ocr: local`. The local adapter loads PaddleOCR (or Tesseract) from a pre-installed model artefact and processes documents with no outbound network call.

**Acceptance Scenario**:
- A test that blocks outbound network access at the socket level still processes a fixture document through the local adapter.

### User Story 5: Live integration tests are gated (Priority: P2)

Running `pytest` by default skips the live tests for ADI, Datalab, and PaddleOCR-from-HuggingFace. Setting `IRIS_OCR_LIVE_ADI=1` (and the corresponding env vars) enables them, exercising real endpoints with a small set of fixture documents.

**Acceptance Scenario**:
- `make test` finishes without contacting any external OCR service.
- `IRIS_OCR_LIVE_ADI=1 make test` runs the ADI live suite and records results.

### User Story 6: Per-adapter telemetry is captured (Priority: P2)

Every OCR call emits a structured log line and an OTEL span carrying: tenant, Product, document identifier, adapter identifier, page count, total latency, per-page confidence, success or failure, error category.

**Acceptance Scenario**:
- Running a document through any adapter produces an OTEL span with the listed attributes.
- A log line is emitted with the same fields.

### User Story 7: The contract suite catches drift (Priority: P2)

Any change that breaks the shared `OCRResult` shape, or that changes adapter behaviour in an incompatible way, fails the contract suite for that adapter.

**Acceptance Scenario**:
- Removing a field from `OCRResult` fails the contract clauses for every adapter.
- A regression in PaddleOCR's bounding box format (e.g., reversed coordinates) fails the bounding box clause.

## Out of scope

- Cost reporting per adapter. Workstream 004's gateway introduces the cost ledger; OCR cost reporting can follow that pattern in a later wave.
- Concurrent OCR across multiple documents on the same adapter. The adapter contract is single-document; batching is a later optimisation.
- OCR-specific PII redaction. PII handling for OCR output is a later wave (the redaction lives in the LLM gateway because that is the boundary where it matters most).
