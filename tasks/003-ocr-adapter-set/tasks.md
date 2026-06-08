# Tasks 003: OCR Adapter Set

**Workstream**: `003-ocr-adapter-set`
**Spec**: [spec.md](./spec.md)  -  **Plan**: [plan.md](./plan.md)  -  **Contract**: [contracts/ocr-engine.md](./contracts/ocr-engine.md)
**Markers**: `[P]` parallelisable, `[US#]` user-story tag, `[size: S|M|L]`, `[owner: AuroPro]`.

## Sprint 1: Protocol + selector

- [x] **T030** `[US2] [size: S] [owner: AuroPro]` Add `iris_engine/contracts/ocr_engine.py` containing the Protocol, result types, and error types from the contract document.
      **Acceptance**: mypy strict passes; the module imports cleanly with zero adapter dependencies.

- [ ] **T031** `[P] [US1] [size: M] [owner: AuroPro]` Implement `iris_engine/ocr/selector.py` that reads `ProductConfig.adapters.ocr` and returns the registered `OCREngine` instance. Includes the optional fallback path from `adapters.ocr_fallback`.
      **Acceptance**: Unit tests cover (a) primary success, (b) primary `OCRUnavailable` followed by fallback success, (c) primary and fallback both fail, surfacing the primary error.

- [ ] **T032** `[P] [US7] [size: M] [owner: AuroPro]` Implement `iris_engine/ocr/in_memory.py` with `InMemoryOCREngine` returning canned `OCRResult` values. Used as a fixture by every adapter test plus the agent tests in workstream 005.
      **Acceptance**: The in-memory engine passes every clause of the contract suite.

## Sprint 1: Adapter packages (parallel)

- [ ] **T033** `[P] [US1] [US3] [size: L] [owner: AuroPro]` `packages/iris-adapters/ocr-adi/`: Azure Document Intelligence adapter. HTTP client over `httpx.AsyncClient`. Maps ADI's analysis result to `OCRResult`. Typed errors for 401, 403, 429, 5xx, timeout.
      **Acceptance**: Unit tests with mocked ADI responses pass every contract clause; live clause runs under `IRIS_OCR_LIVE_ADI=1`.

- [ ] **T034** `[P] [US1] [US3] [size: L] [owner: AuroPro]` `packages/iris-adapters/ocr-datalab/`: Datalab adapter. Reuses Datalab client patterns from the PoCs but with the new error taxonomy.
      **Acceptance**: Unit tests pass; live clause runs under `IRIS_OCR_LIVE_DATALAB=1`.

- [ ] **T035** `[P] [US1] [US4] [size: L] [owner: AuroPro]` `packages/iris-adapters/ocr-paddleocr/`: PaddleOCR adapter. Loads the model from Hugging Face on startup (or from a pre-baked path in the image). Handles PDF page rasterisation via PyMuPDF, runs OCR per page, assembles markdown.
      **Acceptance**: Unit tests pass against bundled fixtures; the airgapped clause C-OCR-LOCAL-001 also passes when `IRIS_PADDLEOCR_OFFLINE=1`.

- [ ] **T036** `[P] [US1] [US4] [size: M] [owner: AuroPro]` `packages/iris-adapters/ocr-local/`: Tesseract adapter. Wraps `pytesseract`. Handles PDF via PyMuPDF page rasterisation, then Tesseract per page.
      **Acceptance**: Unit tests pass with bundled fixtures; the airgapped clause passes.

## Sprint 1: Contract suite

- [ ] **T037** `[US7] [size: M] [owner: AuroPro]` `tests/contract/test_ocr_contract.py`: parametrised contract suite over every registered adapter (in-memory, plus the four real adapters with mocked externals).
      **Acceptance**: All clauses C-OCR-001 through C-OCR-011 pass for every registered adapter under `make test`.

## Sprint 1: Observability

- [ ] **T038** `[P] [US6] [size: S] [owner: AuroPro]` Wrap every adapter's `extract` in an OTEL span recording the attributes listed in spec User Story 6. Emit a structured log line on success and on each typed error.
      **Acceptance**: Running a fixture document through any adapter produces a span with the expected attributes; integration test verifies the span shape.

## Sprint 1: Documentation

- [ ] **T039** `[P] [size: S] [owner: AuroPro]` Document each adapter's setup, credentials, and limitations in `packages/iris-adapters/ocr-<name>/README.md`. Include the env vars each adapter reads.
      **Acceptance**: A team member can install and exercise any adapter using only the package README.

## Definition of Done

1. All four adapters pass the full contract suite.
2. `make test` runs in under three minutes without contacting any external OCR service.
3. `IRIS_OCR_LIVE_<NAME>=1 make test` exercises the named adapter against its real endpoint with one fixture.
4. A document submitted under a Product with `adapters.ocr: paddleocr` is processed by the PaddleOCR adapter (verified by adapter telemetry).
5. A `503` from an ADI primary with a configured fallback routes successfully to the fallback (verified by integration test).
