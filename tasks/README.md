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
- `[size: S | M | L]` rough effort. `S` is half a day, `M` is one to two days, `L` is three to five days.
- `[owner: AuroPro]` for every task in this wave. Individual assignees are recorded in the project tracker rather than in this file.

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

## Estimated total effort

| Workstream | Tasks | Rough effort |
|---|---|---|
| 001 Project scaffold | 7 | 1 week, 1 engineer |
| 002 Configuration framework | 8 | 1 to 1.5 weeks, 1 engineer |
| 003 OCR adapter set | 11 | 2 to 3 weeks, 1 engineer |
| 004 LLM adapter set | 11 | 2 to 3 weeks, 1 engineer |
| 005 Classification + extraction agents | 10 | 1.5 to 2 weeks, 1 engineer |

With two to three engineers running 003 and 004 in parallel, this wave is a four to six week effort start-to-finish, ending with a working configuration-driven pipeline that can ingest a document, OCR it through any of the four OCR providers, classify and extract fields using any of the four LLM providers, and emit a structured result.
