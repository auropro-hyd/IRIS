# Plan 002: Configuration Framework

**Workstream**: `002-configuration-framework`
**Status**: Draft
**Specification**: [spec.md](./spec.md)

## Approach

A Pydantic model per file in the bundle. A loader that walks `config/products/*/*/`, parses every `*.yaml`, validates against the Pydantic schema, and returns a registry. The CLI is a thin wrapper around the loader that returns appropriate exit codes for CI.

The PoC's `ClassificationConfig` Pydantic model is the inspiration for the taxonomy schema. We will lift the field set and tighten the validation.

## Proposed file layout

```
packages/iris-config/
├── pyproject.toml
└── src/iris_config/
    ├── __init__.py            # ProductConfig, ProductRegistry, load_products()
    ├── schema/
    │   ├── __init__.py
    │   ├── product.py         # ProductSchema (root)
    │   ├── adapters.py        # AdaptersSchema (ocr, llm, blob, sor, ...)
    │   ├── taxonomy.py        # TaxonomySchema (lifted from PoC classification_config)
    │   ├── extraction.py      # ExtractionSchema (FNOL field set with validators)
    │   └── prompts.py         # PromptSchema (template paths + variables)
    ├── loader.py              # walk config/products/, load every bundle
    ├── validator.py           # error formatting for CLI
    └── exceptions.py          # ConfigLoadError, ConfigValidationError

tools/iris-cli/
└── src/iris_cli/commands/
    └── config.py              # `iris config validate <path>`

config/products/
└── commercial-auto-claims/
    └── in/
        ├── product.yaml
        ├── taxonomy.yaml
        ├── extraction.yaml
        └── prompts/
            ├── classify.j2
            ├── extract.j2
            └── summarize.j2

packages/iris-config/tests/
├── test_loader.py
├── test_validator.py
├── test_schema_product.py
├── test_schema_taxonomy.py
├── test_schema_extraction.py
└── fixtures/
    ├── valid-bundle/
    └── invalid-bundles/
        ├── missing-taxonomy/
        ├── unknown-ocr-adapter/
        └── duplicate-doc-type/
```

## Key choices

1. **Pydantic v2** for the schema. Type hints, validation, JSON Schema export for free.
2. **JSON Schema export**. `iris config schema product` outputs the JSON Schema; the team can attach it to YAML files in IDEs for editor-time validation.
3. **Strict on unknown keys**. A typo in a YAML field name fails the load. The error message names the bundle, the file, the field path, and the unknown key.
4. **Enum-backed adapter selection**. `AdaptersSchema.ocr: Literal["adi", "datalab", "paddleocr", "local"]`. The four valid options are the ones from workstream 003. When 003 adds a fifth, the enum updates.
5. **Bundle path is the identifier**. `<line-of-business>/<jurisdiction>` is the Product slug. No identifiers in the YAML; the path is authoritative.

## Out of scope

- A Product editor UI.
- Diff and merge of Product bundles across environments. Bundles are environment-specific; promotion is a copy-and-edit, not a merge.

## Dependencies

- Workstream 001 (scaffold) must be complete; `iris-config` package skeleton exists.
- No runtime dependency on adapters; the validation references adapter names only.
