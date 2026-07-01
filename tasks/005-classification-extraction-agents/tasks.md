# Tasks 005: Classification and Extraction Agents

**Workstream**: `005-classification-extraction-agents`
**Spec**: [spec.md](./spec.md)  -  **Plan**: [plan.md](./plan.md)
**Markers**: `[P]` parallelisable, `[US#]` user-story tag, `[size: S|M|L]`, `[owner: AuroPro]`.

## Sprint 2: Result types and template loading

- [x] **T051** `[size: S] [owner: AuroPro]` Define `iris_agents/results.py` with `Classification`, `Extraction`, `FieldValidationError`, and `MissingDocument`. Map directly to the PoC's `ClassificationResponse` shape, tightened with Pydantic v2.
      **Acceptance**: Round-trip with `model_validate` works for the bundled fixtures.

- [x] **T052** `[P] [US6] [size: M] [owner: AuroPro]` Implement `iris_agents/templates.py` that loads a Jinja2 environment scoped to a Product bundle's `prompts/` directory.
      **Acceptance**: Loading a template with an undeclared variable raises a clear error at load time, not at render time.

- [x] **T053** `[P] [size: S] [owner: AuroPro]` Define `iris_agents/errors.py` with `AgentError`, `AgentLLMError` (wraps `LLMError`), and `AgentValidationError`.
      **Acceptance**: `make typecheck` is clean.

## Sprint 2: DocumentClassifier

- [ ] **T054** `[US1] [US2] [US4] [US6] [size: L] [owner: AuroPro]` Implement `DocumentClassifier` in `iris_agents/classifier.py`. Lifts the PoC's classifier flow: render `prompts/classify.j2` with the OCR result and the taxonomy; call `LLMProvider.complete` with the `Classification` schema; return the typed result.
      **Acceptance**: Unit tests against `StubLLMProvider` produce a populated `Classification` and an `unknown` outcome for an off-taxonomy stub response.

- [ ] **T055** `[P] [US8] [size: S] [owner: AuroPro]` Wrap classifier calls in an OTEL span carrying the attributes listed in spec User Story 8.
      **Acceptance**: Integration test verifies the span shape.

## Sprint 2: FieldExtractor

- [ ] **T056** `[US3] [US4] [US6] [size: L] [owner: AuroPro]` Implement `FieldExtractor` in `iris_agents/extractor.py`. Renders `prompts/extract.j2`; calls `LLMProvider.complete` with a dynamically-built Pydantic schema generated from the Product's `extraction.yaml`.
      **Acceptance**: Unit tests against `StubLLMProvider` produce populated extractions; a stub that returns missing required fields surfaces an `AgentValidationError`.

- [ ] **T057** `[P] [size: M] [owner: AuroPro]` Implement per-field validators (regex, enum, range, ISO 8601 date) inside the extractor. Validation failures appear as `FieldValidationError` entries in the result, not exceptions.
      **Acceptance**: A fixture with a known bad date and a known bad enum produces two `FieldValidationError` entries; the rest of the extraction is still returned.

## Sprint 2: Integration matrix

- [ ] **T058** `[US4] [US5] [size: M] [owner: AuroPro]` Integration test matrix in `tests/integration/test_agent_matrix.py`. Parametrised across (OCR adapter x LLM adapter), using the in-memory and stub adapters by default and the real adapters when the corresponding `IRIS_*_LIVE_*` env vars are set.
      **Acceptance**: Every cell of the default matrix returns populated `Classification` and `Extraction`.

## Sprint 2: Golden set

- [ ] **T059** `[P] [US7] [size: M] [owner: AuroPro]` Author the initial golden-set fixtures: 10 FNOL fixtures (taken from the PoC `attached_assets/`), with expected `classification.json` and `extraction.json` per fixture.
      **Acceptance**: `make test-golden` runs against the stub LLM and reports the per-Product accuracy.

- [ ] **T060** `[US7] [size: M] [owner: AuroPro]` Implement `tests/test_golden.py` (gated on `pytest -m golden`) that runs the matrix against the live LLM adapter named in `IRIS_GOLDEN_LLM` and reports accuracy against the Product's declared minimum.
      **Acceptance**: A deliberate prompt regression drops accuracy below the threshold and fails the test.

## Definition of Done

1. `DocumentClassifier` and `FieldExtractor` work for the `commercial-auto-claims/in` Product against the in-memory OCR and the stub LLM.
2. Both agents work against the four LLM adapters (verified by the matrix test).
3. Both agents work against the four OCR adapters (verified by the matrix test).
4. The golden set runs in CI under a flag and produces an accuracy report.
5. OTEL spans cover every agent call.
