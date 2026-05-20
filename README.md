# IRIS

**Insurance Reference Intelligence Stack**. An architecture proposal for a multi-tenant, audit-first insurance claims and underwriting platform.

This repository contains the design proposal, the supporting diagrams, and the first-wave task breakdown for the team. It is not an implementation repository; the implementation will land in a separate repo scaffolded under workstream 001.

## What is in here

| Path | Purpose |
|---|---|
| [`docs/architecture/architecture.md`](docs/architecture/architecture.md) | The narrative architecture proposal. Reads top-to-bottom in about fifteen minutes. |
| [`docs/architecture/iris-architecture.drawio`](docs/architecture/iris-architecture.drawio) | Six-tab editable diagram set covering context, components, request flow, the trust model, deployment topology, and the proposed rollout. |
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

Total wave estimate: three to four weeks elapsed with two to three engineers running 003 and 004 in parallel, calibrated for AI-assisted development at a junior engineer pace.

## Contributing

`main` is protected on this repository. All changes land through reviewed pull requests; direct pushes to `main` are rejected by GitHub.

The expected flow per task:

1. Cut a feature branch named after the task identifier, for example `T031-ocr-selector`.
2. Open a draft pull request as soon as the first commit lands on the branch.
3. Mark the PR ready for review when the acceptance criteria are satisfied.
4. At least one approving review is required. Squash-merge is the default.
5. Delete the feature branch after merge.

The same protection rules apply on the implementation repo once it is scaffolded under workstream 001.

## Status

The contents of this repository describe a **proposal**, not a deployed system. Phases described in the rollout section indicate intended deliverables, not completion state.

## Copyright

Copyright (c) 2026 Auropro. All rights reserved. No license is granted for use, modification, or redistribution.
