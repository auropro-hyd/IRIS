# Tasks 001: Project Scaffold

**Workstream**: `001-project-scaffold`
**Spec**: [spec.md](./spec.md)  -  **Plan**: [plan.md](./plan.md)
**Markers**: `[P]` parallelisable, `[US#]` user-story tag, `[size: S|M|L]`, `[owner: AuroPro]`.

## Sprint 0: Scaffold

### Repo and workspace

- [x] **T001** `[US1] [size: S] [owner: AuroPro]` Initialise `iris/` mono-repo with `uv init`, configure `[tool.uv.workspace]` to list every member.
      **Acceptance**: `uv sync --all-packages` succeeds against an empty workspace and produces a populated `.venv`.

- [x] **T002** `[P] [US1] [size: S] [owner: AuroPro]` Create empty `pyproject.toml` per workspace member under `apps/`, `packages/iris-*`, `packages/iris-adapters/*`, `tools/iris-cli`.
      **Acceptance**: Each package imports as a namespace; `uv pip list` shows all of them installed in editable mode.

- [x] **T003** `[P] [US3] [size: S] [owner: AuroPro]` Add `import-linter` configuration enforcing apps → packages → adapters → infrastructure boundary.
      **Acceptance**: `lint-imports` returns zero on the empty scaffold; a deliberate violation test PR is rejected.

### Tooling

- [x] **T004** `[US1] [size: S] [owner: AuroPro]` Add `Makefile` with targets `install`, `dev`, `up`, `down`, `lint`, `typecheck`, `test`, `test-cov`, `clean`.
      **Acceptance**: Every target returns zero on a fresh clone.

- [ ] **T005** `[P] [US1] [size: M] [owner: AuroPro]` Add `pytest` config: markers `contract`, `integration`, `e2e`; coverage threshold 80 percent on `iris-engine`.
      **Acceptance**: `make test` runs the placeholder suite; `make test-cov` produces an HTML report under `htmlcov/`.

- [ ] **T006** `[P] [US1] [size: S] [owner: AuroPro]` Add `ruff` and `mypy` configuration. mypy in strict mode for `iris-engine` and adapters; relaxed for tests.
      **Acceptance**: `make lint` and `make typecheck` return zero on the scaffold.

### Dev compose

- [ ] **T007** `[US1] [size: M] [owner: AuroPro]` Author `compose.dev.yaml` with Postgres (custom image bundling pgvector and Apache AGE) and Redis. Port-remap to avoid collisions with other local stacks.
      **Acceptance**: `make up` starts both services; `make dev` brings the API up at `http://localhost:8088` and the API returns `200` on `/healthz`.

### CI for the codebase

- [ ] **T008** `[P] [US2] [size: M] [owner: AuroPro]` Add `.github/workflows/ci.yml` running `make lint`, `make typecheck`, `make test`, `make test-cov` on `pull_request` and `push` to `main`. Runs alongside the existing `docs-ci.yml`. Adds these as required status checks on `main` once the workflow has run at least once.
      **Acceptance**: A test PR triggers the workflow; failure on any target fails the PR. The four `ci.yml` jobs appear in the required-status-check list on the `main` branch protection rule.

### Docs

- [ ] **T009** `[P] [US1] [size: S] [owner: AuroPro]` Extend the root `README.md` with a dev-loop section (clone, install, run, tests) and author `.env.example` with the variables the scaffold reads (`IRIS_ENV`, `IRIS_DATABASE_URL`, `IRIS_REDIS_URL`, `IRIS_DEV_AUTH`).
      **Acceptance**: A new engineer follows the README and reaches a working `/healthz` in under fifteen minutes.

### Docs CI

- [x] **T010** `[P] [US4] [size: S] [owner: AuroPro]` `.github/workflows/docs-ci.yml` is in place. Two jobs.
      1. **Markdown lint**: `markdownlint-cli` against every `*.md` under `docs/`, `tasks/`, and the root-level prose files, using `.markdownlint.json` for the rule set.
      2. **Tasks structural check**: `scripts/check-tasks.py` asserts every workstream folder has `spec.md`, `plan.md`, `tasks.md`; every `tasks.md` has at least one `T0xx` task line; every `spec.md` carries the required frontmatter keys.
      **Acceptance**:
      - A test PR that removes any required file from a workstream folder fails the workflow.
      - A test PR that introduces a markdown style violation fails the workflow.
      - A test PR with a malformed task line (missing the `T0xx` identifier) fails the structural check.
      - The workflow runs on `pull_request` and on `push` to `main`. **Already in place.**

### Dependency and security hygiene

- [ ] **T011** `[P] [size: M] [owner: AuroPro]` Extend the existing dependency and security setup to cover the codebase as it lands.
      1. **`.github/dependabot.yml`** (currently covers `github-actions` only) gains three more ecosystems as the codebase appears: `pip` (or `uv` once Dependabot supports it, otherwise the generated `requirements.txt`), `npm` (workbench), and `docker` (Dockerfiles under `docker/`). Weekly schedule, label `dependencies`, auto-request the architect via `CODEOWNERS`. Group minor + patch updates per ecosystem to keep PR volume low.
      2. **CodeQL** workflow at `.github/workflows/codeql.yml` scanning Python and JavaScript / TypeScript. Default queries plus `security-extended`. Runs on PR and on a weekly schedule. Added once the first non-trivial code lands.
      3. **`SECURITY.md`** is already in place; updated to mention any new reporting surface as new components ship.
      4. **Branch protection on `main`** is already in place; gains additional required status checks as the new CI jobs from T008 and the CodeQL job appear.
      **Acceptance**:
      - `dependabot.yml` parses cleanly per `https://github.com/auropro-hyd/IRIS/network/updates` and lists at least four ecosystems once the codebase lands.
      - The CodeQL workflow completes a baseline scan with zero high-severity findings on the initial scaffold.
      - `lint`, `typecheck`, `test`, `test-cov`, `codeql` are all required status checks on `main`.

### Pre-commit hygiene

- [ ] **T012** `[P] [size: S] [owner: AuroPro]` Extend the existing `.pre-commit-config.yaml` (currently markdownlint + structural check) with the Python and secrets-scanning hooks needed once code lands. Hooks added:
      1. `ruff` (lint) and `ruff-format` against staged Python files.
      2. `mypy --strict` against staged Python files in `iris-engine` and the adapter packages.
      3. `pyupgrade` to keep syntax current with the project's Python version.
      4. `check-merge-conflict`, `check-toml`, and `check-added-large-files` from `pre-commit/pre-commit-hooks`.
      5. `detect-secrets` with a checked-in `.secrets.baseline`.
      6. `gitleaks` as a second-pass secret scanner.
      The `Makefile` from T004 grows a `make pre-commit-install` target that wires the hooks into `.git/hooks/`. The CI workflow from T008 also runs `pre-commit run --all-files` as one of its steps so the same gates apply on PRs even if a contributor skips the local hook.
      **Acceptance**:
      - Running `pre-commit run --all-files` on a fresh clone after `make pre-commit-install` returns zero.
      - A test PR introducing trailing whitespace fails the local hook and the CI gate.
      - A test PR introducing an obvious secret (`OPENAI_API_KEY=sk-...`) is rejected by `detect-secrets` or `gitleaks`.
      - The best-practices document at `docs/engineering/best-practices.md` lists the final hook set as the canonical local gate; any change here must be mirrored there.

## Definition of Done for this workstream

1. A fresh clone reaches `/healthz` `200` in under fifteen minutes following `README.md`.
2. `make lint`, `make typecheck`, `make test`, `make test-cov` all return zero on the scaffold.
3. The `ci.yml` workflow is green on `main` and gates every PR.
4. The `docs-ci.yml` workflow stays green on `main` and gates every PR (already in place).
5. Import-linter rejects a reverse-import test PR.
