# Tasks 002: Configuration Framework

**Workstream**: `002-configuration-framework`
**Spec**: [spec.md](./spec.md)  -  **Plan**: [plan.md](./plan.md)
**Markers**: `[P]` parallelisable, `[US#]` user-story tag, `[size: S|M|L]`, `[owner: AuroPro]`.

## Sprint 0: Schema

- [ ] **T020** `[US1] [size: M] [owner: AuroPro]` Lift the PoC's `ClassificationConfig` (in `claims-intake-automation/backend/models/classification_config.py` and the identical copy in `Submission-Workbench-v2`) into `iris_config/schema/taxonomy.py`. Tighten validation: document types must be unique; required-documents list must reference declared types.
      **Acceptance**: Importing the schema raises a clear `pydantic.ValidationError` on each violation.

- [ ] **T021** `[P] [US1] [size: M] [owner: AuroPro]` Author `iris_config/schema/product.py` with `ProductSchema` (region, retention, adapters reference, taxonomy reference, extraction reference, prompts reference).
      **Acceptance**: A round-trip dump and reload of a valid bundle produces a stable representation.

- [ ] **T022** `[P] [US1] [size: M] [owner: AuroPro]` Author `iris_config/schema/adapters.py` with `AdaptersSchema`. The `ocr` and `llm` fields use `Literal` types listing the adapters from workstreams 003 and 004.
      **Acceptance**: A bundle with `adapters.ocr: paddel-ocr` fails validation with the exact list of valid values in the error message.

- [ ] **T023** `[P] [US1] [size: M] [owner: AuroPro]` Author `iris_config/schema/extraction.py` covering FNOL fields with their per-field validators (regex, enum, range).
      **Acceptance**: A field with an invalid regex pattern fails validation at load time with the file path and field path in the error.

- [ ] **T024** `[P] [US1] [size: S] [owner: AuroPro]` Author `iris_config/schema/prompts.py` covering template paths plus declared variables.
      **Acceptance**: A template that references a variable not declared in the schema fails validation.

## Sprint 0: Loader

- [ ] **T025** `[US1] [US2] [size: M] [owner: AuroPro]` Implement `iris_config.loader.load_products(root: Path) -> ProductRegistry`. Walks every `<lob>/<jurisdiction>/` directory under `root`. Returns a registry keyed by slug.
      **Acceptance**: Loading the fixtures returns the expected number of Products; a malformed bundle raises `ConfigLoadError` naming the bundle and the file.

- [ ] **T026** `[US3] [size: S] [owner: AuroPro]` Implement `iris_config.validator` with rich error formatting: bundle slug, file path, field path, invalid value, suggested fix.
      **Acceptance**: Each of the three `invalid-bundles/*` fixtures produces an error message with all four elements.

## Sprint 0: CLI and example bundle

- [ ] **T027** `[US4] [size: S] [owner: AuroPro]` Implement `iris config validate <path>` CLI command in `tools/iris-cli`. Exit code 0 on success, non-zero on validation failure.
      **Acceptance**: Running against `valid-bundle/` returns 0; running against any `invalid-bundles/*` returns 1.

- [ ] **T028** `[P] [US1] [size: M] [owner: AuroPro]` Create the `commercial-auto-claims/in/` example bundle covering every section of the schema, sized for realism (15 to 20 document types, 25 to 30 extraction fields).
      **Acceptance**: The bundle validates clean and is referenced from the README as the starter Product.

## Sprint 0: Tests

- [ ] **T029** `[P] [size: M] [owner: AuroPro]` Unit tests for every schema module under `packages/iris-config/tests/test_schema_*.py`. Coverage target: 95 percent on `iris_config/schema/`.
      **Acceptance**: `make test-cov` shows 95 percent or higher on the schema package.

## Definition of Done

1. Loading the `commercial-auto-claims/in` bundle returns a populated `ProductConfig`.
2. `iris config validate config/products/` is wired into CI and gates PRs.
3. Three negative fixtures (`missing-taxonomy`, `unknown-ocr-adapter`, `duplicate-doc-type`) all produce well-formatted error messages.
4. JSON Schema export for `ProductSchema` is published to `docs/schemas/product.schema.json`.

## Estimated effort

10 tasks, 1 engineer, 1 to 1.5 weeks. Tasks T020 to T024 can run in parallel.
