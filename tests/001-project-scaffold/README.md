# Workstream 001: project scaffold acceptance tests

**Workstream**: `001-project-scaffold`  
**Tasks**: [`tasks/001-project-scaffold/tasks.md`](../../tasks/001-project-scaffold/tasks.md)  
**Plan**: [`tasks/001-project-scaffold/plan.md`](../../tasks/001-project-scaffold/plan.md)

This folder holds **acceptance tests for workstream 001 tasks**. Names mirror `tasks/001-project-scaffold/`. They are not unit, contract, integration, or e2e tests (see [`tests/README.md`](../README.md) and [`docs/engineering/best-practices.md`](../../docs/engineering/best-practices.md)).

Add or update a `test_t0xx_<short-name>.py` file when a task’s acceptance criteria need automated checks at repo level. Update the task table below in the same PR.

## Before running tests

From the repository root, install all workspace members **once** before pytest in this folder (except T001-only layout checks):

```bash
uv sync --all-packages
```

This creates `.venv` and editable installs for every uv member. T002 import checks, T002 `uv pip list`, T003 `lint-imports`, and `uv run lint-imports` all need this step. Slow tests do not run `uv sync` for you.

**T001-only exception:** layout and workspace config tests do not require sync:

```bash
uv run pytest tests/001-project-scaffold/test_t001_workspace.py -v
```

## How to run

Run `uv sync --all-packages` first (see above), then:

```bash
# Fast default (T001 layout + T002 imports + T003 config; no slow subprocesses)
uv run pytest tests/001-project-scaffold/ -v

# Full acceptance including slow checks (uv sync, uv pip list, lint-imports)
uv run pytest tests/001-project-scaffold/ -v -m slow

# T001 only (layout + workspace config; sync not required)
uv run pytest tests/001-project-scaffold/test_t001_workspace.py -v

# T002 only
uv run pytest tests/001-project-scaffold/test_t002_editable_packages.py -v
uv run pytest tests/001-project-scaffold/test_t002_editable_packages.py -v -m slow

# T003 only
uv run pytest tests/001-project-scaffold/test_t003_import_linter.py -v
uv run pytest tests/001-project-scaffold/test_t003_import_linter.py -v -m slow

# import-linter directly (after uv sync)
uv run lint-imports
```

Root [`pyproject.toml`](../../pyproject.toml) sets `addopts = ["-m", "not slow"]`, so default pytest skips subprocess-heavy checks. Run with `-m slow` for `uv sync` (T001), `uv pip list` (T002), `lint-imports` (T003), and the `make <target>` subprocess checks (T004). T004 wires `make install` to `uv sync --all-packages` and `make test` to the default pytest invocation, preserving this `-m slow` behaviour.

## Pytest markers used here

| Marker | Meaning |
|---|---|
| `slow` | Subprocess or cold-cache work (`uv sync --all-packages`, `uv pip list`, `lint-imports`, `make <target>` invocations). Excluded from default runs. |

Other markers (`contract`, `integration`, `e2e`) are registered in T005 and used under `tests/contract/`, `tests/integration/`, and `tests/e2e/`.

## Task coverage

| Task | Test module | Status | What it verifies |
|---|---|---|---|
| **T001** | `test_t001_workspace.py` | Done | Root uv workspace members; each member `pyproject.toml`; plan directory layout; workbench not a uv member; `@pytest.mark.slow` uv sync creates `.venv` |
| **T002** | `test_t002_editable_packages.py` | Done | `test_each_namespace_imports` (fast); `@pytest.mark.slow` `test_uv_pip_list_shows_all_members_editable` |
| **T003** | `test_t003_import_linter.py` | Done | Three import-linter contracts (layers, adapter independence, mid-package forbidden); fast config tests; `@pytest.mark.slow` `lint-imports` |
| **T004** | `test_t004_makefile.py` | Done | Root `Makefile` declares the nine T004 `.PHONY` targets, each has a recipe, `make -n <target>` parses, and `@pytest.mark.slow` runs `make <target>` for guarded targets to confirm exit zero |
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
5. Run `uv sync --all-packages`, then `uv run pytest tests/001-project-scaffold/ -v` and, if you added or changed `slow` tests, `uv run pytest tests/001-project-scaffold/ -v -m slow`.

## Conventions

- **File names**: `test_t0xx_<short-slug>.py` matching the task id in `tasks.md`.
- **Imports**: stdlib first; use `tomllib` (Python 3.12+), not `tomli`.
- **Repo root**: `REPO_ROOT = Path(__file__).resolve().parents[2]` for paths relative to the mono-repo root.
- **Shared constants**: reuse helpers from earlier task modules only when it reduces duplication (for example `EXPECTED_WORKSPACE_MEMBERS` and `MEMBER_SRC_PACKAGES` from `test_t001_workspace.py` in T002); avoid circular imports.

### T001 vs T002

| | T001 | T002 |
|---|---|---|
| Focus | Workspace exists; directory layout | Hatchling editable packages |
| Slow tests | `test_uv_sync_all_packages_creates_venv` (`uv sync`) | `test_uv_pip_list_shows_all_members_editable` (`uv pip list`) |
| Fast tests | Layout and workspace config (9 tests) | `test_each_namespace_imports` |
| Typical run | `uv sync --all-packages` first; default pytest; `-m slow` for subprocess checks | Same sync step required before imports or `uv pip list` |
| Why not `tests/contract` or `tests/integration`? | Scaffold milestones for workstream 001 only; see [`tests/README.md`](../README.md) |

### T003 import boundaries

`[tool.importlinter]` in root `pyproject.toml` uses **Python import roots** (underscores), not repo paths (hyphens).

Three contracts:

1. **Layers** (top to bottom): apps/CLI → mid-packages → adapters → `iris_engine`.
2. **Independence:** the eight adapter packages must not import each other.
3. **Forbidden:** `iris_agents`, `iris_data`, `iris_config`, `iris_observability` must not import concrete adapters (apps wire adapters at the composition root).

Manual violation checks (revert before merge):

```bash
uv sync --all-packages
# engine → adapter (layers contract)
# import iris_ocr_adi in packages/iris-engine/src/iris_engine/__init__.py
# mid-package → adapter (forbidden contract)
# import iris_ocr_adi in packages/iris-agents/src/iris_agents/__init__.py
uv run lint-imports   # expect exit 1
```

When workstream 001 is complete, new feature work should add tests under `tests/{contract,integration,e2e}/`, not new files here unless a later task explicitly extends the scaffold.
