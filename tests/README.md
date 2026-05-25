# IRIS tests

How tests are organised in this repository. The canonical rules for each layer live in [`docs/engineering/best-practices.md`](../docs/engineering/best-practices.md) (section 3, Testing).

## Standard test layers

| Layer | Path | When to use |
|---|---|---|
| Unit | `packages/<pkg>/tests/test_*.py` | One module, no I/O, fast |
| Contract | `tests/contract/test_*.py` | Every adapter must satisfy a Protocol |
| Integration | `tests/integration/test_*.py` | Two or more components together |
| End-to-end | `tests/e2e/test_*.py` | Real services; gated on `IRIS_E2E_LIVE=1` |

Run the default suite from the repo root (once `Makefile` lands in T004, prefer `make test`):

```bash
uv run pytest
```

## Workstream acceptance tests

While a workstream is being built out, **task-level acceptance** for that workstream lives under:

```
tests/<workstream-id>-<slug>/
```

The folder name mirrors [`tasks/`](../tasks/): for example `tasks/001-project-scaffold/` pairs with `tests/001-project-scaffold/`.

| Workstream | Acceptance tests |
|---|---|
| 001 Project scaffold | [`001-project-scaffold/`](./001-project-scaffold/) |
| 002 Configuration framework | (unit and contract tests under `packages/iris-config/` and `tests/contract/` when implemented) |
| 003 OCR adapter set | `tests/contract/` (not under `tests/003-*`) |
| 004 LLM adapter set | `tests/contract/` (not under `tests/004-*`) |
| 005 Agents | `packages/iris-agents/tests/` and `tests/integration/` |

Workstream folders are for **scaffolding and milestone checks** tied to `tasks.md` entries. Ongoing product tests use the four standard layers above, not a per-workstream tree.

Each workstream acceptance folder has its own `README.md` listing files, markers, and commands. Update that README when a new task adds or changes acceptance tests.
