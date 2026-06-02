# Security policy

This repository is the home of IRIS: the architecture proposal, the task breakdown, and the production codebase as it is built. We take security seriously across all three.

## What to report

- A secret, credential, or personal identifier accidentally committed to this repository.
- A vulnerability in any GitHub Action referenced from `.github/workflows/` or in any third-party dependency used by the codebase.
- A supply-chain risk in any tool referenced from CI, pre-commit hooks, or the production stack.
- A flaw in the task structural check (`scripts/check-tasks.py`) that could let unsafe content land on `main`.
- A code-level vulnerability anywhere under `apps/`, `packages/`, or `tools/`. The components now in the tree are: the FastAPI service (`apps/api`), the async worker (`apps/worker`), and the React workbench (`apps/workbench`).

## Automated scanning

CodeQL runs on every pull request and on a weekly schedule via `.github/workflows/codeql.yml`. It scans Python (the engine, adapters, API, and worker) and JavaScript / TypeScript (the workbench) using the default query suite plus `security-extended`. Any high-severity finding blocks merge. If you discover a finding that CodeQL missed, report it through the channel below rather than referencing the scan result in a public issue.

## How to report

Open a **private vulnerability report** through the GitHub Security tab on this repository:

`https://github.com/auropro-hyd/IRIS/security/advisories/new`

Or email the architect directly. Do not file a public issue, do not open a public PR demonstrating the vulnerability, and do not post details in any channel that is visible outside the maintainers.

Please include:

- A short description of the issue.
- Reproduction steps or a pointer to the offending commit / file.
- Your assessment of severity and any suggested mitigation.

## What to expect

- Acknowledgement within two working days.
- An initial assessment within five working days.
- A fix or a documented decision to accept the risk within ten working days, depending on severity.

## Out of scope for this repository

- Architectural disagreements with the proposal. Open a regular issue or PR instead.
- Security findings against external systems referenced in the proposal (Azure OpenAI, Azure AD, Guidewire, etc.). Report those to the relevant vendor.

## Maintainers

- Architect: Anmol Jaiswal (`@anmolg1997`)
- Owner organisation: AuroPro
