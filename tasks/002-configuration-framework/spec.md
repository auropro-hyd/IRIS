# Specification 002: Configuration Framework

**Workstream**: `002-configuration-framework`
**Status**: Draft
**Input**: Akhilesh's request that the core services "have to be configurable with a configuration file like in PoC."

## Background

Both PoCs already drive behaviour through a YAML file (look at `backend/models/classification_config.py` in either repo for the shape they use). The pattern is good. The PoC implementation is not reusable as-is because:

1. It is single-tenant. There is no concept of per-tenant or per-Product configuration.
2. It is scattered. Classification config lives in one file; OCR config in another; LLM endpoints in environment variables.
3. It is not validated. A typo in the YAML surfaces as a runtime `KeyError`, not a startup-time error with a useful message.

This workstream lifts the YAML pattern, formalises it into "Product bundles," and provides a loader plus validator. Subsequent workstreams (003, 004, 005) consume the framework but do not depend on its internals.

## Goals

1. A YAML schema for a "Product bundle" that holds the adapter selection, the classification taxonomy, the field extraction schema, the prompt templates, and the policy rules for one line of business in one jurisdiction.
2. A loader that reads a Product bundle, validates it, and returns a typed `ProductConfig` object.
3. A CLI command that validates a bundle without loading it into a running app, so the team can validate bundles in CI.
4. One example bundle (`commercial-auto-claims/in`) that exercises every section of the schema.

## Non-goals

- Hot reloading. Configuration is loaded at startup; changing it requires a restart.
- A configuration UI. The bundles are author-time YAML; the workbench will surface them read-only later.
- Secrets management. Secrets stay in environment variables or a vault; the bundle never holds raw credentials. References use the `secret://path` notation that the outbound gateway already understands.

## User Scenarios and Testing

### User Story 1: A developer adds a new Product (Priority: P1)

A developer creates `config/products/property-fire-claims/in/` with the four files that make up a Product bundle. They run `iris config validate config/products/property-fire-claims/in/`, which returns zero with no errors. They start the API; the new Product appears in `GET /v1/products`.

**Acceptance Scenario**:
- `iris config validate` returns zero on a well-formed bundle.
- `iris config validate` returns non-zero with a precise error message ("missing required field `taxonomy.document_types`") on a malformed bundle.
- The API exposes `GET /v1/products` listing every loaded Product.

### User Story 2: An adapter selection changes per Product (Priority: P1)

Two Products in the same deployment select different OCR providers. `commercial-auto-claims/in` selects `paddleocr`. `property-fire-claims/in` selects `datalab`. The OCR engine routes each Product's documents through its configured adapter.

**Acceptance Scenario**:
- Two Products load with different `adapters.ocr` selections.
- A test that submits a document under each Product confirms the right adapter is invoked.

### User Story 3: A bundle that references an unknown adapter fails fast (Priority: P1)

A developer typos the OCR adapter name as `paddel-ocr`. The loader rejects the bundle at startup with a message naming the invalid key and the valid options.

**Acceptance Scenario**:
- `iris config validate` returns non-zero.
- The error message includes the file path, the field path (`adapters.ocr`), the invalid value (`paddel-ocr`), and the list of valid values (`adi`, `datalab`, `paddleocr`, `local`).

### User Story 4: Configuration is validated in CI (Priority: P2)

The CI workflow runs `iris config validate config/products/` against every bundle. A malformed bundle fails the PR.

**Acceptance Scenario**:
- A test PR with a malformed bundle fails CI on the `config-validate` step.

## Bundle structure (informative)

```
config/products/<line-of-business>/<jurisdiction>/
├── product.yaml             # adapter selection, model params, region, retention
├── taxonomy.yaml            # classification taxonomy (document types, required docs)
├── extraction.yaml          # field extraction schema (FNOL fields, validators)
└── prompts/                 # prompt templates referenced by the agents
    ├── classify.j2
    ├── extract.j2
    └── summarize.j2
```

A formal JSON Schema for each file lands in this workstream.

## Out of scope

- Hot reloading.
- Per-tenant overrides of a Product bundle (later wave; the model is one tenant → one Product selection per LOB and jurisdiction).
- Workflow CEL rules (later wave; the rule slot exists in the schema but the evaluator does not).
