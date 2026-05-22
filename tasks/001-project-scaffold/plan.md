# Plan 001: Project Scaffold

**Workstream**: `001-project-scaffold`
**Status**: Draft
**Specification**: [spec.md](./spec.md)

## Approach

A `uv` workspace at the repo root. Three application packages under `apps/`, five engine packages under `packages/iris-*`, two empty adapter package skeletons under `packages/iris-adapters/` to lock in the layout, and a `tools/` folder for the CLI. A `Makefile` orchestrates the developer commands. `docker compose` brings the runtime dependencies up.

## Proposed file layout

The workspace lives at the root of this repository, alongside the existing `docs/`, `tasks/`, `.github/`, `scripts/`, and root-level documents. New directories introduced by this workstream are marked **new**.

```
.
├── apps/                       # new
│   ├── api/                    # FastAPI service
│   │   ├── pyproject.toml
│   │   └── src/iris_api/
│   ├── worker/                 # arq worker
│   │   ├── pyproject.toml
│   │   └── src/iris_worker/
│   └── workbench/              # React + Vite (placeholder, no UI yet this wave)
│       ├── package.json
│       └── src/
├── packages/                   # new
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
├── tools/                      # new
│   └── iris-cli/               # admin + ops CLI
├── tests/                      # new
│   ├── contract/               # Protocol contract suites
│   ├── integration/
│   └── e2e/                    # gated on IRIS_E2E_LIVE=1
├── config/                     # new
│   └── products/               # YAML Product bundles (workstream 002)
├── docker/                     # new
│   ├── api.Dockerfile
│   └── worker.Dockerfile
├── docs/                       # exists; design + engineering docs
├── tasks/                      # exists; the work breakdown
├── scripts/                    # exists; grows with operational helpers
├── .github/                    # exists; gains `workflows/ci.yml`
├── compose.dev.yaml            # new
├── Makefile                    # new
├── pyproject.toml              # new; workspace root
├── README.md                   # exists; extended with the dev-loop section
├── .pre-commit-config.yaml     # exists; extended in T012
└── .env.example                # new
```

## Key choices

1. **uv workspace** rather than pip + setuptools. Faster resolves, single lock file across packages, plays well with editable installs.
2. **pyproject.toml per package**. Each workspace member is independently installable so the team can publish individual packages later.
3. **Strict mypy + ruff in CI**. Lint and type-check are blocking gates from day one.
4. **`import-linter`** for the cross-layer rules described in spec User Story 3.
5. **A `compose.dev.yaml` with only Postgres + Redis for now**. The OCR-server and LLM-server containers land in workstreams 003 and 004 respectively.
6. **A `pytest` configuration with markers**: `contract`, `integration`, `e2e`. Default test run excludes `e2e`.
7. **Two CI workflows in `.github/workflows/`**. `docs-ci.yml` (already in place) lints the markdown and runs the tasks structural check. `ci.yml` (added in this workstream) runs lint, type-check, test, and coverage on the Python and TS code as it lands. Independent jobs; one is for prose, the other for code.

## Out of scope

- Real CI runners. The workflow file lands; choosing GitHub Actions vs. GitLab CI is whatever the team is on.
- Container registries. The Dockerfile lands; the publish pipeline is a later concern.
