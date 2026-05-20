# Security policy

This repository holds the IRIS architecture proposal and the first-wave task breakdown. It contains no application code, no production data, and no credentials.

The supporting risks are still real and small. If you find any of the following, please report rather than disclose publicly.

## What to report

- A secret, credential, or personal identifier accidentally committed to this repository.
- A vulnerability in any GitHub Action referenced from `.github/workflows/` that affects this repo or the implementation repo (`iris`).
- A supply-chain risk in the `markdownlint-cli` invocation or any dependency added in future PRs.
- A flaw in the task structural check (`scripts/check-tasks.py`) that could let unsafe content land on `main`.

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
- Code-level vulnerabilities in IRIS itself. Those should be reported against the implementation repository once it exists.

## Maintainers

- Architect: Anmol Jaiswal (`@anmolg1997`)
- Owner organisation: AuroPro
