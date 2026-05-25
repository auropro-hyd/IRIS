# Workstream 001: project scaffold acceptance tests

**Workstream**: `001-project-scaffold`  
**Tasks**: [`tasks/001-project-scaffold/tasks.md`](../../tasks/001-project-scaffold/tasks.md)  
**Plan**: [`tasks/001-project-scaffold/plan.md`](../../tasks/001-project-scaffold/plan.md)

This folder holds **acceptance tests for workstream 001 tasks**. Names mirror `tasks/001-project-scaffold/`. They are not unit, contract, integration, or e2e tests (see [`tests/README.md`](../README.md) and [`docs/engineering/best-practices.md`](../../docs/engineering/best-practices.md)).

Add or update a `test_t0xx_<short-name>.py` file when a task’s acceptance criteria need automated checks at repo level. Update the task table below in the same PR.

## How to run

From the repository root:

```bash
# Fast default: layout and config checks only (no uv sync subprocess)
uv run pytest tests/001-project-scaffold/ -v

# Full workstream 001 acceptance including slow checks
uv run pytest tests/001-project-scaffold/ -v -m slow

# T001 only (layout + workspace config; still excludes slow uv sync)
uv run pytest tests/001-project-scaffold/test_t001_workspace.py -v

# T002 only (editable installs; run after uv sync)
uv run pytest tests/001-project-scaffold/test_t002_editable_packages.py -v
```

**Prerequisite for T002 tests:** install workspace members once:

```bash
uv sync --all-packages
```

Root [`pyproject.toml`](../../pyproject.toml) sets `addopts = ["-m", "not slow"]`, so **`uv sync` is not run** during a normal `pytest` invocation. T001’s `test_uv_sync_all_packages_creates_venv` is the slow check that runs it explicitly (`-m slow`). After T004, `make test` should keep that behaviour.

## Pytest markers used here

| Marker | Meaning |
|---|---|
| `slow` | Subprocess or cold-cache work (for example `uv sync --all-packages`). Excluded from default runs. |

Other markers (`contract`, `integration`, `e2e`) are registered in T005 and used under `tests/contract/`, `tests/integration/`, and `tests/e2e/`.

## Task coverage

| Task | Test module | Status | What it verifies |
|---|---|---|---|
| **T001** | `test_t001_workspace.py` | Done | Root uv workspace members; each member `pyproject.toml`; plan directory layout; workbench not a uv member; `@pytest.mark.slow` uv sync creates `.venv` |
| **T002** | `test_t002_editable_packages.py` | Planned | Each namespace imports; `uv pip list` shows editable installs (lands in PR #11) |
| **T003** | (TBD) | Planned | `import-linter` config; `lint-imports` clean on scaffold |
| **T004** | (TBD) | Planned | `Makefile` targets exist and succeed |
| **T005** | (TBD) | Planned | pytest markers, coverage gate on `iris-engine` |
| **T006** | (TBD) | Planned | `ruff` / `mypy` config |
| **T007** | (TBD) | Planned | `compose.dev.yaml`, `/healthz` (may live under `tests/integration/`) |
| **T008** | (TBD) | Planned | CI workflow (usually validated in CI, not pytest) |
| **T009** | (TBD) | Planned | README dev loop, `.env.example` |
| **T010** | N/A | Done elsewhere | `docs-ci.yml` |
| **T011** | (TBD) | Planned | Dependabot, CodeQL |
| **T012** | (TBD) | Planned | pre-commit hooks |

## Adding a test for a new task

1. Create `test_t0xx_<slug>.py` in this folder (one file per task is enough unless the task is large).
2. Prefer **fast, deterministic** checks in the default run; use `@pytest.mark.slow` for subprocesses, network, or multi-second setup.
3. Add a row to the **Task coverage** table above.
4. Mark the task `[x]` in `tasks/001-project-scaffold/tasks.md` when acceptance criteria pass.
5. Run `uv run pytest tests/001-project-scaffold/ -v` and, if you added or changed `slow` tests, `uv run pytest tests/001-project-scaffold/ -v -m slow`.

## Conventions

- **File names**: `test_t0xx_<short-slug>.py` matching the task id in `tasks.md`.
- **Imports**: stdlib first; use `tomllib` (Python 3.12+), not `tomli`.
- **Repo root**: `REPO_ROOT = Path(__file__).resolve().parents[2]` for paths relative to the mono-repo root.
- **Shared constants**: reuse helpers from earlier task modules only when it reduces duplication (for example `EXPECTED_WORKSPACE_MEMBERS` and `MEMBER_SRC_PACKAGES` from `test_t001_workspace.py` in T002); avoid circular imports.

### T001 vs T002

| | T001 | T002 |
|---|---|---|
| Focus | Workspace exists; directory layout; stubs may use `package = false` | Members are real packages (hatchling + `src/`) |
| Typical run | Default pytest (fast); `-m slow` for uv sync | After `uv sync --all-packages` |
| Why not `tests/contract` or `tests/integration`? | Scaffold milestones for workstream 001 only; see [`tests/README.md`](../README.md) |

When workstream 001 is complete, new feature work should add tests under `tests/{contract,integration,e2e}/`, not new files here unless a later task explicitly extends the scaffold.
