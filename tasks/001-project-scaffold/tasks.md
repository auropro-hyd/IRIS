# Tasks 001: Project Scaffold

**Workstream**: `001-project-scaffold`
**Spec**: [spec.md](./spec.md)  -  **Plan**: [plan.md](./plan.md)
**Markers**: `[P]` parallelisable, `[US#]` user-story tag, `[size: S|M|L]`, `[owner: TBD]`.

## Sprint 0: Scaffold

### Repo and workspace

- [ ] **T001** `[US1] [size: S] [owner: TBD]` Initialise `iris/` mono-repo with `uv init`, configure `[tool.uv.workspace]` to list every member.
      **Acceptance**: `uv sync --all-packages` succeeds against an empty workspace and produces a populated `.venv`.

- [ ] **T002** `[P] [US1] [size: S] [owner: TBD]` Create empty `pyproject.toml` per workspace member under `apps/`, `packages/iris-*`, `packages/iris-adapters/*`, `tools/iris-cli`.
      **Acceptance**: Each package imports as a namespace; `uv pip list` shows all of them installed in editable mode.

- [ ] **T003** `[P] [US3] [size: S] [owner: TBD]` Add `import-linter` configuration enforcing apps → packages → adapters → infrastructure boundary.
      **Acceptance**: `lint-imports` returns zero on the empty scaffold; a deliberate violation test PR is rejected.

### Tooling

- [ ] **T004** `[US1] [size: S] [owner: TBD]` Add `Makefile` with targets `install`, `dev`, `up`, `down`, `lint`, `typecheck`, `test`, `test-cov`, `clean`.
      **Acceptance**: Every target returns zero on a fresh clone.

- [ ] **T005** `[P] [US1] [size: M] [owner: TBD]` Add `pytest` config: markers `contract`, `integration`, `e2e`; coverage threshold 80 percent on `iris-engine`.
      **Acceptance**: `make test` runs the placeholder suite; `make test-cov` produces an HTML report under `htmlcov/`.

- [ ] **T006** `[P] [US1] [size: S] [owner: TBD]` Add `ruff` and `mypy` configuration. mypy in strict mode for `iris-engine` and adapters; relaxed for tests.
      **Acceptance**: `make lint` and `make typecheck` return zero on the scaffold.

### Dev compose

- [ ] **T007** `[US1] [size: M] [owner: TBD]` Author `compose.dev.yaml` with Postgres (custom image bundling pgvector and Apache AGE) and Redis. Port-remap to avoid collisions with other local stacks.
      **Acceptance**: `make up` starts both services; `make dev` brings the API up at `http://localhost:8088` and the API returns `200` on `/healthz`.

### CI

- [ ] **T008** `[P] [US2] [size: M] [owner: TBD]` Add `.github/workflows/ci.yml` (or GitLab equivalent) running `make lint`, `make typecheck`, `make test`, `make test-cov` on `pull_request` and `push` to `main`.
      **Acceptance**: A test PR triggers the workflow; failure on any target fails the PR.

### Docs

- [ ] **T009** `[P] [US1] [size: S] [owner: TBD]` Author `README.md` covering clone, install, dev loop, tests. Author `.env.example` with the variables the scaffold reads (`IRIS_ENV`, `IRIS_DATABASE_URL`, `IRIS_REDIS_URL`, `IRIS_DEV_AUTH`).
      **Acceptance**: A new engineer follows the README and reaches a working `/healthz` in under fifteen minutes.

## Definition of Done for this workstream

1. A fresh clone reaches `/healthz` `200` in under fifteen minutes following `README.md`.
2. `make lint`, `make typecheck`, `make test`, `make test-cov` all return zero on the scaffold.
3. CI workflow is green on `main`.
4. Import-linter rejects a reverse-import test PR.

## Estimated effort

7 tasks, 1 engineer, 1 week.
