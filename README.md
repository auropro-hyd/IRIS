# IRIS

**Insurance Reference Intelligence Stack**. A multi-tenant, audit-first insurance claims and underwriting platform.

This repository is the home of IRIS: the architecture proposal, the supporting diagrams, the first-wave task breakdown, and (as the team executes the tasks) the production codebase. Design lives in `docs/` and `tasks/`; code lands at the repository root under `apps/`, `packages/`, `tools/`, and `tests/` as it is built.

## What is in here

| Path | Purpose |
|---|---|
| [`docs/architecture/architecture.md`](docs/architecture/architecture.md) | The narrative architecture proposal. Reads top-to-bottom in about fifteen minutes. |
| [`docs/architecture/iris-architecture.drawio`](docs/architecture/iris-architecture.drawio) | Six-tab editable diagram set covering context, components, request flow, the trust model, deployment topology, and the proposed rollout. |
| [`docs/engineering/best-practices.md`](docs/engineering/best-practices.md) | Engineering conventions: coding standards, pre-commit hygiene, testing, observability, error handling, security, AI-assisted development, and dependency management. The canonical reference for *how* the code is written. |
| [`tasks/`](tasks/) | First-wave work breakdown. Five workstreams, each with a spec, a plan, and a concrete task list. Start at [`tasks/README.md`](tasks/README.md). |

## Where to start

- **Reviewing the proposal**: open [`architecture.md`](docs/architecture/architecture.md). The mermaid diagrams render directly in the GitHub UI.
- **Reviewing the diagrams**: open [`iris-architecture.drawio`](docs/architecture/iris-architecture.drawio) in [draw.io](https://app.diagrams.net) (File → Open) or in VS Code via the **Draw.io Integration** extension. Six tabs at the bottom of the canvas: Context, Components, Pipeline, Tenancy/RBAC/Audit, Deployment, Roadmap.
- **Picking up a task**: open [`tasks/README.md`](tasks/README.md). It indexes the five workstreams and explains the task identifier convention, sizing, and dependencies between workstreams.

## Architecture proposal at a glance

[`architecture.md`](docs/architecture/architecture.md) is structured in nine numbered sections:

1. Executive Summary
2. Context: the existing proofs-of-concept
3. Proposed Approach
4. Proposed Architecture (layers, request flow, trust model, adapter pattern)
5. Proposed Deployment Topology
6. Proposed Rollout
7. Key Design Decisions
8. Prerequisites from Stakeholders
9. References

## First-wave workstreams

The five workstreams in [`tasks/`](tasks/), in dependency order:

| # | Workstream | Folder |
|---|---|---|
| 001 | Project scaffold (mono-repo layout, tooling, dev loop, CI) | [`tasks/001-project-scaffold/`](tasks/001-project-scaffold/) |
| 002 | Configuration framework (YAML Product bundles) | [`tasks/002-configuration-framework/`](tasks/002-configuration-framework/) |
| 003 | OCR adapter set (ADI, Datalab, PaddleOCR, locally-hosted) | [`tasks/003-ocr-adapter-set/`](tasks/003-ocr-adapter-set/) |
| 004 | LLM adapter set (Azure OpenAI, Anthropic, OpenAI, locally / privately hosted) | [`tasks/004-llm-adapter-set/`](tasks/004-llm-adapter-set/) |
| 005 | Classification and extraction agents | [`tasks/005-classification-extraction-agents/`](tasks/005-classification-extraction-agents/) |

The wave parallelises across 003 and 004 once 002 is in. Workstream 005 depends on both. Sequencing details are in [`tasks/README.md`](tasks/README.md).

## Local development

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/), [uv](https://docs.astral.sh/uv/getting-started/installation/), `make`, Python 3.12.

```bash
# 1. Clone and install workspace packages
git clone https://github.com/auropro-hyd/IRIS.git
cd IRIS
make install

# 2. Copy environment variables and adjust if needed
cp .env.example .env

# 3. Start backing services (Postgres on :5488, Redis on :6399)
make up

# 4. Start the API with hot-reload (http://localhost:8088)
make dev
```

Verify the stack is healthy:

```bash
curl http://localhost:8088/healthz
# {"status":"ok"}
```

Run the test suite:

```bash
make test       # fast suite (excludes slow and e2e)
make test-cov   # with coverage report in htmlcov/
```

Stop services when done:

```bash
make down
```

Other useful targets: `make distclean` removes `.venv/` and Docker volumes for a full reset; `make status` shows which services are running.

## Product bundles

A **Product bundle** is the YAML configuration that drives one line of business in one jurisdiction. Every bundle lives under `config/products/<line-of-business>/<jurisdiction>/` and contains four parts:

| File / Directory | Contents |
|---|---|
| `product.yaml` | Adapter selection (`ocr`, `llm`), region, data retention period, and prompt template declarations |
| `taxonomy.yaml` | Document type catalogue and required-document list |
| `extraction.yaml` | Ordered list of FNOL fields with per-field validators (regex, range, allowed values) |
| `prompts/` | Jinja2 templates for the classify, extract, and summarise agents |

**Starter example: `commercial-auto-claims/in/`**

[`config/products/commercial-auto-claims/in/`](config/products/commercial-auto-claims/in/) is the reference bundle for commercial auto claims. It covers all schema sections: 18 document types, 28 extraction fields spanning every field type and validator, and three prompt templates. Copy this directory when creating a new Product and edit the fields to match the target line of business and jurisdiction.

## Contributing

`main` is protected on this repository. All changes land through reviewed pull requests; direct pushes to `main` are rejected by GitHub.

The expected flow per task:

1. Cut a feature branch named after the task identifier, for example `T031-ocr-selector`.
2. Open a draft pull request as soon as the first commit lands on the branch.
3. Mark the PR ready for review when the acceptance criteria are satisfied.
4. At least one approving review is required. Squash-merge is the default.
5. Delete the feature branch after merge.

The same rules apply to every change, whether to docs, tasks, or the codebase as it lands.

## Status

The contents of this repository describe a **proposal**, not a deployed system. Phases described in the rollout section indicate intended deliverables, not completion state.

## Copyright

Copyright (c) 2026 Auropro. All rights reserved. No license is granted for use, modification, or redistribution.
