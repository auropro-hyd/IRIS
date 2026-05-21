# Tasks 001: Project Scaffold

**Workstream**: `001-project-scaffold`
**Spec**: [spec.md](./spec.md)  -  **Plan**: [plan.md](./plan.md)
**Markers**: `[P]` parallelisable, `[US#]` user-story tag, `[size: S|M|L]`, `[owner: AuroPro]`.

## Sprint 0: Scaffold

### Repo and workspace

- [ ] **T001** `[US1] [size: S] [owner: AuroPro]` Initialise `iris/` mono-repo with `uv init`, configure `[tool.uv.workspace]` to list every member.
      **Acceptance**: `uv sync --all-packages` succeeds against an empty workspace and produces a populated `.venv`.

- [ ] **T002** `[P] [US1] [size: S] [owner: AuroPro]` Create empty `pyproject.toml` per workspace member under `apps/`, `packages/iris-*`, `packages/iris-adapters/*`, `tools/iris-cli`.
      **Acceptance**: Each package imports as a namespace; `uv pip list` shows all of them installed in editable mode.

- [ ] **T003** `[P] [US3] [size: S] [owner: AuroPro]` Add `import-linter` configuration enforcing apps → packages → adapters → infrastructure boundary.
      **Acceptance**: `lint-imports` returns zero on the empty scaffold; a deliberate violation test PR is rejected.

### Tooling

- [ ] **T004** `[US1] [size: S] [owner: AuroPro]` Add `Makefile` with targets `install`, `dev`, `up`, `down`, `lint`, `typecheck`, `test`, `test-cov`, `clean`.
      **Acceptance**: Every target returns zero on a fresh clone.

- [ ] **T005** `[P] [US1] [size: M] [owner: AuroPro]` Add `pytest` config: markers `contract`, `integration`, `e2e`; coverage threshold 80 percent on `iris-engine`.
      **Acceptance**: `make test` runs the placeholder suite; `make test-cov` produces an HTML report under `htmlcov/`.

- [ ] **T006** `[P] [US1] [size: S] [owner: AuroPro]` Add `ruff` and `mypy` configuration. mypy in strict mode for `iris-engine` and adapters; relaxed for tests.
      **Acceptance**: `make lint` and `make typecheck` return zero on the scaffold.

### Dev compose

- [ ] **T007** `[US1] [size: M] [owner: AuroPro]` Author `compose.dev.yaml` with Postgres (custom image bundling pgvector and Apache AGE) and Redis. Port-remap to avoid collisions with other local stacks.
      **Acceptance**: `make up` starts both services; `make dev` brings the API up at `http://localhost:8088` and the API returns `200` on `/healthz`.

### CI on the implementation repo

- [ ] **T008** `[P] [US2] [size: M] [owner: AuroPro]` Add `.github/workflows/ci.yml` (or GitLab equivalent) on the implementation repo running `make lint`, `make typecheck`, `make test`, `make test-cov` on `pull_request` and `push` to `main`.
      **Acceptance**: A test PR triggers the workflow; failure on any target fails the PR.

### Docs

- [ ] **T009** `[P] [US1] [size: S] [owner: AuroPro]` Author `README.md` covering clone, install, dev loop, tests. Author `.env.example` with the variables the scaffold reads (`IRIS_ENV`, `IRIS_DATABASE_URL`, `IRIS_REDIS_URL`, `IRIS_DEV_AUTH`).
      **Acceptance**: A new engineer follows the README and reaches a working `/healthz` in under fifteen minutes.

### Docs CI on the proposal repo

- [ ] **T010** `[P] [US4] [size: S] [owner: AuroPro]` Add `.github/workflows/docs-ci.yml` to the proposal repo (`auropro-hyd/IRIS`). Two jobs.
      1. **Markdown lint**: run `markdownlint-cli` against every `*.md` under `docs/` and `tasks/`, using a checked-in `.markdownlint.json` for the rule set.
      2. **Tasks structural check**: a small script under `scripts/check-tasks.py` that walks `tasks/*/` and asserts (a) every workstream folder contains `spec.md`, `plan.md`, `tasks.md`; (b) every `tasks.md` has at least one task line matching `^- \[ \] \*\*T\d{3,}\*\*`; (c) every spec.md has the required frontmatter keys (`Workstream`, `Status`, `Architect`).
      **Acceptance**:
      - A test PR that removes `tasks/003-ocr-adapter-set/plan.md` fails the workflow.
      - A test PR that introduces a markdown style violation fails the workflow.
      - A test PR with a malformed task line (missing the `T0xx` identifier) fails the structural check.
      - The workflow runs on `pull_request` and on `push` to `main`.

### Dependency and security hygiene on the implementation repo

- [ ] **T011** `[P] [size: M] [owner: AuroPro]` Wire dependency-update automation and a baseline security posture on the implementation repo from day one. Four pieces.
      1. **`.github/dependabot.yml`** covering four ecosystems: `pip` (or `uv` once Dependabot supports it, otherwise the generated `requirements.txt`), `npm` (workbench), `docker` (Dockerfiles under `docker/`), and `github-actions`. Weekly schedule, label `dependencies`, auto-request the architect via `CODEOWNERS`. Group minor + patch updates per ecosystem to keep PR volume low.
      2. **CodeQL** workflow at `.github/workflows/codeql.yml` scanning Python and JavaScript / TypeScript. Default queries plus `security-extended`. Runs on PR and on a weekly schedule.
      3. **`SECURITY.md`** at the implementation-repo root, modeled on the proposal-repo file. Lists what to report, the private-vulnerability-report URL, and the architect as the maintainer contact.
      4. **Branch protection on `main`** mirroring the proposal repo: PR required, one approving review, linear history, no force push, no deletion. Required status checks: `lint`, `typecheck`, `test`, `test-cov`, `codeql`.
      **Acceptance**:
      - `dependabot.yml` parses cleanly per `https://github.com/<owner>/<repo>/network/updates`.
      - The CodeQL workflow completes a baseline scan with zero high-severity findings on the empty scaffold.
      - `SECURITY.md` is reachable on the GitHub Security tab.
      - A direct push to `main` on the implementation repo is rejected by GitHub.
      - A PR that fails any required status check cannot be merged without admin bypass.

### Pre-commit hygiene on the implementation repo

- [ ] **T012** `[P] [size: S] [owner: AuroPro]` Add `.pre-commit-config.yaml` on the implementation repo so every contributor's commits are gated locally before they reach the PR. Hooks at minimum:
      1. `ruff` (lint) and `ruff-format` against staged Python files.
      2. `mypy --strict` against staged Python files in `iris-engine` and the adapter packages.
      3. `pyupgrade` to keep syntax current with the project's Python version.
      4. `trailing-whitespace`, `end-of-file-fixer`, `check-merge-conflict`, `check-yaml`, `check-toml` from `pre-commit/pre-commit-hooks`.
      5. `detect-secrets` with a checked-in baseline.
      6. `gitleaks` as a second-pass secret scanner.
      The `Makefile` from T004 grows a `make pre-commit-install` target that wires the hooks into `.git/hooks/`. The CI workflow from T008 also runs `pre-commit run --all-files` as one of its steps so the same gates apply on PRs even if a contributor skips the local hook.
      **Acceptance**:
      - Running `pre-commit run --all-files` on a fresh clone after `make pre-commit-install` returns zero.
      - A test PR introducing trailing whitespace fails the local hook and the CI gate.
      - A test PR introducing an obvious secret (`OPENAI_API_KEY=sk-...`) is rejected by `detect-secrets` or `gitleaks`.
      - The best-practices document at `docs/engineering/best-practices.md` in the proposal repo lists this hook set as the canonical local gate; any change here must be mirrored there.

## Definition of Done for this workstream

1. A fresh clone of the implementation repo reaches `/healthz` `200` in under fifteen minutes following `README.md`.
2. `make lint`, `make typecheck`, `make test`, `make test-cov` all return zero on the scaffold.
3. The implementation-repo CI workflow is green on `main`.
4. The proposal-repo docs CI workflow is green on `main` and gates every PR.
5. Import-linter rejects a reverse-import test PR.
