# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

IRIS (Insurance Reference Intelligence Stack) is a **proposal and planning repository** — no application source code lives here. The implementation mono-repo will be scaffolded under workstream 001. Everything here describes what to build and how to build it.

## Commands

Install and run pre-commit hooks locally:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Lint markdown directly:

```bash
npm install -g markdownlint-cli@0.41.0
markdownlint 'docs/**/*.md' 'tasks/**/*.md' README.md
```

Validate task folder structure:

```bash
python3 scripts/check-tasks.py
```

Both checks also run in CI (`.github/workflows/docs-ci.yml`) on every PR and push to main. That workflow is already implemented in this repo.

## Repository structure

```
docs/architecture/architecture.md   # 9-section architecture proposal — read this first
docs/architecture/iris-architecture.drawio  # Six-tab diagrams (draw.io)
docs/engineering/best-practices.md  # Canonical coding standards for the implementation repo
tasks/                              # First-wave work broken into 5 workstreams
  001-project-scaffold/             # Mono-repo, tooling, dev loop, CI
  002-configuration-framework/      # YAML Product bundles
  003-ocr-adapter-set/              # ADI, Datalab, PaddleOCR, local adapters
  004-llm-adapter-set/              # Azure OpenAI, Anthropic, OpenAI, local adapters
  005-classification-extraction-agents/
scripts/check-tasks.py              # Structural validator for tasks/
```

Each workstream folder contains `spec.md`, `plan.md`, and `tasks.md`. The OCR and LLM workstreams also carry typed Protocol contracts under `contracts/`.

## Planned architecture (four layers)

**Apps** (thin orchestrators): `iris-api` (FastAPI), `iris-worker` (arq), `iris-workbench` (React)

**Packages** (all business logic): `iris-engine` (Protocols, types, workflow, gateways), `iris-agents` (extraction, classification), `iris-data` (schema, RLS, Alembic), `iris-config`, `iris-observability`

**Adapters** (one per external system): LLM providers, OCR engines, bus (Redis Streams), identity (OIDC), SoR, knowledge stores (pgvector + Apache AGE), blob, outbound

**Infrastructure**: Postgres + pgvector + Apache AGE, Redis, blob storage (S3/Azure/MinIO in dev)

The engine takes adapters as constructor parameters (dependency injection). Configuration selects the active adapter per tenant Product. Two gateway decorators wrap adapters: Model Gateway (PII redaction, cost cap, region pinning, audit) and Outbound Gateway (egress allowlist, rate limit, secrets vault, audit).

**Request flow**: intake → OCR → extraction → enrichment → classification → workflow → HITL/STP → outbound. Each arrow is a Redis Streams event; the bus is the source of truth for the audit chain.

**Trust model**: `tenant_id` is the leading column of every table key and index; RLS on every table; six RBAC roles (tenant_admin, engineer, underwriter, adjuster, auditor, ops); hash-chained `workflow_events` ledger per case.

## Task conventions

Task identifiers follow the pattern `T0xx` (e.g., `T031`). Branch names use `T0xx-slug`. Each task line in `tasks.md` must match `- [ ] **T0xx**`. Tasks marked `[P]` are parallelisable — their branches can be cut and worked concurrently. The `check-tasks.py` script enforces the task line format and rejects em-dashes and en-dashes anywhere under `tasks/`.

Every `spec.md` must carry these frontmatter keys or `check-tasks.py` will fail: `Workstream`, `Status`, `Architect`, `Input`.

Workstream dependency order: 001 → 002 → (003 ∥ 004 ∥ 005 scaffold). Workstream 005 acceptance depends on 003 and 004 being complete.

**Out of scope for the first wave** (deferred to later): event bus workers, workflow state machine, multi-tenancy/RBAC enforcement on the API, knowledge store, SoR outbound adapters.

## Contribution rules

- Branch off main as `T0xx-slug`; open a draft PR immediately
- One approving review required; squash merge; delete the branch
- CODEOWNERS auto-requests @anmolg1997 on every PR
- No direct pushes to main

## Writing style enforced by CI

- No em-dashes (`—`) or en-dashes (`–`) anywhere in `.md` files under `tasks/`
- Titles and commit messages lead with a verb
- Tables for comparisons; plain English prose
- Markdownlint rules are in `.markdownlint.json` (MD033 raw HTML allowed; fenced code blocks required)

## Key standards for the implementation repo

The full reference is `docs/engineering/best-practices.md`. Critical points:

- **Python**: ruff (line length 100), mypy --strict, async by default, structlog with correlation IDs, typed exceptions from `iris_engine.errors`
- **TypeScript**: eslint + prettier, tsc --strict, React Query for server state, Tailwind + CSS Modules
- **SQL**: Alembic migrations, `tenant_id` as leading column of every key/index, RLS on every table
- **Dependencies**: uv + uv.lock (Python), pnpm + pnpm-lock.yaml (JS), image digests in docker compose; lockfiles always committed
- **Testing**: 80% coverage target on iris-engine and adapters; stub all external adapters; property-based tests (hypothesis) for parsers/validators
- **Observability**: OTEL spans at every network/DB/process boundary with `tenant_id`, `correlation_id`, `adapter_id`, `outcome`, `latency_ms`, `input_tokens`, `output_tokens`; never log API keys, JWT, raw prompts, or PII
- **No**: `Any` without justification, `# type: ignore` without comment, TODO without a tracking issue, silent fallbacks, commented-out code, magic numbers
- **Make targets** (once 001 is scaffolded): `make lint`, `make fmt`, `make typecheck`, `make test`, `make test-cov`, `make contract`, `make e2e`
