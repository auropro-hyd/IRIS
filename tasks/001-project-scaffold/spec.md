# Specification 001: Project Scaffold

**Workstream**: `001-project-scaffold`
**Status**: Draft
**Architect**: Anmol Jaiswal
**Input**: Direction to scaffold the project and break the work down so the team can execute against discrete tasks.

## Background

The IRIS proposal describes a four-layer architecture: apps, packages, adapters, infrastructure. None of that code exists today. The team needs a working mono-repo, a dev loop, a test harness, and a CI lane before any feature work can be picked up. This workstream produces that foundation and nothing else.

## Goals

1. A single mono-repo, named `iris`, that hosts every workspace member.
2. A dev loop that brings the stack up on a laptop in one command.
3. A test harness that runs the unit and contract suites with a single command and produces coverage reports.
4. A continuous integration lane on the implementation repo that runs the same commands on push.
5. A docs CI lane on the proposal repo (`auropro-hyd/IRIS`) that validates the architecture and task documents on every PR.

## Non-goals

This workstream does not implement any feature. It produces the empty package skeletons, the configuration files, and the developer tooling. Feature code lands in subsequent workstreams.

## User Scenarios and Testing

### User Story 1: A new engineer joins the team (Priority: P1)

A new engineer clones the repo, runs `make install`, then `make dev`, and reaches a working API at `http://localhost:8088`. The engineer can run `make test` to execute the full unit suite, which passes against the scaffold's placeholder code.

**Acceptance Scenario**:
- `git clone` succeeds.
- `make install` returns zero and produces a populated `.venv`.
- `make dev` starts the API and the worker; the API responds `200` on `/healthz`.
- `make test` returns zero with the placeholder tests passing.

### User Story 2: Continuous integration enforces the same gates locally and remotely (Priority: P1)

A pull request triggers a CI workflow that runs the same `make` targets a developer runs locally: lint, type-check, test, coverage. The workflow fails the PR if any target fails.

**Acceptance Scenario**:
- CI configuration exists at `.github/workflows/ci.yml`.
- The workflow runs on `pull_request` and on `push` to `main`.
- The workflow runs `make lint`, `make typecheck`, `make test`, and uploads coverage as an artifact.

### User Story 3: The mono-repo enforces a clean import boundary (Priority: P2)

The packages are arranged so the apps can import the packages, the packages can import the adapters, and the adapters can import only the engine plus their external library. Reverse imports (engine importing an adapter) fail at lint time.

**Acceptance Scenario**:
- `import-linter` rule is configured.
- A test PR that adds a reverse import is rejected by the linter.

### User Story 4: The proposal repo guards its documents in CI (Priority: P2)

A PR against the `auropro-hyd/IRIS` repo triggers a docs CI workflow that lints every markdown file under `docs/` and `tasks/`, and checks the structural conventions of the tasks tree (each workstream folder has `spec.md`, `plan.md`, and `tasks.md`; each `tasks.md` has at least one `T0xx` task identifier). A malformed task list or a missing file fails the workflow.

**Acceptance Scenario**:
- CI configuration exists at `.github/workflows/docs-ci.yml` in the proposal repo.
- A test PR removing one of the three required files from a workstream folder fails the workflow.
- A test PR introducing a markdown style violation (per a checked-in `.markdownlint.json`) fails the workflow.

## Out of scope

- Any real adapter implementation.
- Any real database migration.
- Any real workflow or agent code.

## Open questions

None at this time.
