# Plan 001: Project Scaffold

**Workstream**: `001-project-scaffold`
**Status**: Draft
**Specification**: [spec.md](./spec.md)

## Approach

A `uv` workspace at the repo root. Three application packages under `apps/`, five engine packages under `packages/iris-*`, two empty adapter package skeletons under `packages/iris-adapters/` to lock in the layout, and a `tools/` folder for the CLI. A `Makefile` orchestrates the developer commands. `docker compose` brings the runtime dependencies up.

## Proposed file layout

```
iris/
├── apps/
│   ├── api/                    # FastAPI service
│   │   ├── pyproject.toml
│   │   └── src/iris_api/
│   ├── worker/                 # arq worker
│   │   ├── pyproject.toml
│   │   └── src/iris_worker/
│   └── workbench/              # React + Vite (placeholder, no UI yet this wave)
│       ├── package.json
│       └── src/
├── packages/
│   ├── iris-engine/            # contracts + types + errors
│   ├── iris-agents/            # placeholder for workstream 005
│   ├── iris-data/              # SQLAlchemy models + alembic
│   ├── iris-config/            # YAML loader (workstream 002)
│   ├── iris-observability/     # OTEL, logs, metrics
│   └── iris-adapters/
│       ├── ocr-adi/            # placeholder for workstream 003
│       ├── ocr-datalab/
│       ├── ocr-paddleocr/
│       ├── ocr-local/
│       ├── llm-azure-openai/   # placeholder for workstream 004
│       ├── llm-openai/
│       ├── llm-anthropic/
│       └── llm-local/
├── tools/
│   └── iris-cli/               # admin + ops CLI
├── tests/
│   ├── contract/               # Protocol contract suites
│   ├── integration/
│   └── e2e/                    # gated on IRIS_E2E_LIVE=1
├── config/
│   └── products/               # YAML Product bundles (workstream 002)
├── docker/
│   ├── api.Dockerfile
│   └── worker.Dockerfile
├── scripts/
├── docs/
│   └── architecture/           # links back to the IRIS proposal repo
├── .github/workflows/
│   └── ci.yml
├── compose.dev.yaml
├── Makefile
├── pyproject.toml              # workspace root
├── README.md
└── .env.example
```

## Key choices

1. **uv workspace** rather than pip + setuptools. Faster resolves, single lock file across packages, plays well with editable installs.
2. **pyproject.toml per package**. Each workspace member is independently installable so the team can publish individual packages later.
3. **Strict mypy + ruff in CI**. Lint and type-check are blocking gates from day one.
4. **`import-linter`** for the cross-layer rules described in spec User Story 3.
5. **A `compose.dev.yaml` with only Postgres + Redis for now**. The OCR-server and LLM-server containers land in workstreams 003 and 004 respectively.
6. **A `pytest` configuration with markers**: `contract`, `integration`, `e2e`. Default test run excludes `e2e`.
7. **Two CI workflows, on two different repos**. The implementation repo gets `ci.yml` (lint + type-check + test + coverage). The proposal repo (`auropro-hyd/IRIS`, which holds the architecture documents and this task tree) gets `docs-ci.yml` (markdown lint + structural check on the tasks tree). The two workflows are independent; they share no jobs and no runners.

## Out of scope

- Real CI runners. The workflow file lands; choosing GitHub Actions vs. GitLab CI is whatever the team is on.
- Container registries. The Dockerfile lands; the publish pipeline is a later concern.
