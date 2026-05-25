# IRIS · Tasks · First Wave

**Architect**: Anmol Jaiswal
**Owner**: AuroPro

This folder is the work breakdown for the first wave of IRIS development. The scope is the core services that everything else depends on: configurable OCR ingestion, classification and extraction capabilities, with swappable OCR providers (ADI, Datalab, PaddleOCR via Hugging Face, locally hosted) and swappable LLM providers (Azure OpenAI, Anthropic, OpenAI, locally or privately hosted).

Event-driven architecture details are tracked for a later wave. The work in this folder is sized to land in parallel with that conversation.

## What is in this folder

Five workstreams. Each workstream has its own folder with the same three-file layout we use for all IRIS specs.

| Workstream | Goal | Folder |
|---|---|---|
| 001 | Project scaffold (mono-repo layout, tooling, dev loop) | [`001-project-scaffold/`](./001-project-scaffold/) |
| 002 | Configuration framework (YAML Product bundles, like the PoC pattern) | [`002-configuration-framework/`](./002-configuration-framework/) |
| 003 | OCR adapter set (ADI, Datalab, PaddleOCR, locally-hosted) | [`003-ocr-adapter-set/`](./003-ocr-adapter-set/) |
| 004 | LLM adapter set (Azure OpenAI, Anthropic, OpenAI, locally / privately hosted) | [`004-llm-adapter-set/`](./004-llm-adapter-set/) |
| 005 | Classification and extraction agents (consuming the swappable adapters) | [`005-classification-extraction-agents/`](./005-classification-extraction-agents/) |

## Workstream acceptance tests

Task acceptance for **workstream 001 (scaffold)** is checked under [`tests/001-project-scaffold/`](../tests/001-project-scaffold/). That folder name mirrors this tree (`001-project-scaffold`). Each task that needs automated acceptance should add or update `test_t0xx_<slug>.py` there and document it in [`tests/001-project-scaffold/README.md`](../tests/001-project-scaffold/README.md).

Later workstreams normally use the standard test layers instead of a `tests/00x-*` folder:

- **Unit** tests live in `packages/<pkg>/tests/`.
- **Contract** tests live in `tests/contract/`.
- **Integration** and **e2e** tests live in `tests/integration/` and `tests/e2e/`.

See [`tests/README.md`](../tests/README.md) for the full layout.

## How each workstream is structured

Inside every workstream folder:

- `spec.md` describes what to build, the user-visible behaviour, and the acceptance scenarios.
- `plan.md` describes the proposed file layout and the implementation approach.
- `tasks.md` is the concrete task list. Each task has an identifier, a parallelisation marker, an effort estimate, an owner, and an acceptance criterion.
- For workstreams that introduce a new Protocol, a `contracts/` sub-folder holds the contract definition.

## Task identifier convention

`T0xx` for tasks. Bullet items inside a task are sub-tasks. A typical task line reads:

```
- [ ] T030 [P] [US1] [size: M] [owner: AuroPro] Add iris_engine/contracts/ocr_engine.py
      Acceptance: Protocol type-checks under mypy strict; in-memory fixture passes the
      contract suite from T037.
```

Markers:

- `[P]` parallelisable with other `[P]` tasks in the same section.
- `[US1]` to `[US7]` user-story reference inside the workstream's `spec.md`.
- `[size: S | M | L]` relative complexity. `S` is straightforward and self-contained, `M` requires light design or has multiple steps, `L` involves design choices or significant integration. Wall-clock time depends on the engineer and is tracked in the project tracker rather than in this file.
- `[owner: AuroPro]` for every task in this wave. Individual assignees are recorded in the project tracker rather than in this file.

## Contribution workflow

`main` is protected on this repository. All changes land through pull requests; direct pushes to `main` are rejected by GitHub.

For each task:

1. Cut a feature branch named `T0xx-short-slug` (for example `T031-ocr-selector`).
2. Open a draft pull request as soon as the first commit is on the branch. This makes work visible early.
3. Mark the PR ready for review when the task's acceptance criteria are satisfied.
4. At least one approving review is required before merge. Squash-merge is the default; the PR title becomes the squashed commit message.
5. Delete the feature branch after merge.

The same workflow applies to every change, whether to docs, tasks, or the codebase that grows out of executing the workstreams.

## Dependencies between workstreams

```
001 (scaffold)
  └── 002 (configuration)
        ├── 003 (OCR adapters)
        ├── 004 (LLM adapters)
        └── 005 (classification + extraction agents)
                ├── depends on 003
                └── depends on 004
```

Workstreams 003 and 004 can be picked up in parallel once 002 lands the configuration loader. Workstream 005 can begin its scaffolding and tests in parallel but cannot reach acceptance until both 003 and 004 ship their first adapter.

## What is explicitly out of scope for this wave

The following are tracked for later waves and should not be picked up under this work breakdown:

1. Event bus and worker subscribers. Architectural direction on the event-driven shape is pending; this lands once that direction is locked in.
2. Workflow state machine. Pending event-bus guidance.
3. Multi-tenancy and RBAC enforcement on the API. This wave keeps the dev-mode header trust path; the OIDC integration is a later wave.
4. Knowledge store (vector, page, graph). Later wave.
5. System-of-record outbound adapters. Later wave.

The scope here is intentionally narrow: configurable OCR ingestion, configurable LLM access, and the classification / extraction agents that sit on top.

## Task count

| Workstream | Tasks |
|---|---|
| 001 Project scaffold | 12 |
| 002 Configuration framework | 8 |
| 003 OCR adapter set | 11 |
| 004 LLM adapter set | 11 |
| 005 Classification + extraction agents | 10 |

Wall-clock estimates are intentionally not tracked here. They depend on the engineer, the available AI tooling, and whether the work is happening in focused blocks. The project tracker is the right home for forecasts and burn-down. This file is the source of truth for *what* and *in what order*.

## Sequencing

Once workstream 001 produces the scaffold, the rest of the wave can be parallelised:

- **002** depends on 001.
- **003** and **004** can run in parallel after 002 lands the configuration loader.
- **005** can start scaffolding and tests in parallel with 003 and 004 but cannot reach acceptance until both have shipped their first adapter.

The wave ends with a working configuration-driven pipeline that can ingest a document, OCR it through any of the four OCR providers, classify and extract fields using any of the four LLM providers, and emit a structured result.
