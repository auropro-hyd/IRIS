# IRIS

**Insurance Reference Intelligence Stack** — an architecture proposal for a multi-tenant, audit-first insurance claims and underwriting platform.

This repository contains the design proposal and the supporting diagrams. It is not an implementation repository.

## What is in here

| File | Purpose |
|---|---|
| [`docs/architecture/architecture.md`](docs/architecture/architecture.md) | The narrative architecture proposal. Reads top-to-bottom in about fifteen minutes. |
| [`docs/architecture/iris-architecture.drawio`](docs/architecture/iris-architecture.drawio) | Six-tab editable diagram set covering context, components, request flow, the trust model, deployment topology, and the proposed rollout. |

## How to read the architecture proposal

Start with [`architecture.md`](docs/architecture/architecture.md). It is structured in nine numbered sections:

1. Executive Summary
2. Context: the existing proofs-of-concept
3. Proposed Approach
4. Proposed Architecture (layers, request flow, trust model, adapter pattern)
5. Proposed Deployment Topology
6. Proposed Rollout
7. Key Design Decisions
8. Prerequisites from Stakeholders
9. References

The mermaid diagrams in the markdown render directly in the GitHub UI.

## How to open the drawio file

Either:

- Open [draw.io](https://app.diagrams.net) in a browser and choose **File → Open** → pick the `.drawio` file from a local checkout, or
- In VS Code, install the **Draw.io Integration** extension and open the file directly in the editor.

The diagram is organised as six tabs at the bottom of the canvas:

1. Context
2. Components
3. Pipeline
4. Tenancy, RBAC, Audit
5. Deployment
6. Roadmap (PoCs to IRIS)

## Status

The contents of this repository describe a **proposal**, not a deployed system. Phases described in the rollout section indicate intended deliverables, not completion state.

## Copyright

Copyright (c) 2026 Auropro. All rights reserved. No license is granted for use, modification, or redistribution.
