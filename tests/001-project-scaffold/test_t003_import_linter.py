"""
T003 acceptance: import-linter enforces IRIS layer boundaries on workspace packages.

Default (config only):
  uv run pytest tests/001-project-scaffold/test_t003_import_linter.py -v

Including lint-imports subprocess (slow):
  uv run pytest tests/001-project-scaffold/test_t003_import_linter.py -v -m slow
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest
import tomllib

from test_t001_workspace import MEMBER_SRC_PACKAGES, REPO_ROOT

EXPECTED_ROOT_PACKAGES = frozenset(MEMBER_SRC_PACKAGES.values())

LAYER_CONTRACT_NAME = "IRIS apps, packages, adapters, engine"
INDEPENDENCE_CONTRACT_NAME = "Adapters do not depend on each other"


def _load_importlinter_config() -> dict[str, Any]:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["tool"]["importlinter"]


def test_root_packages_match_workspace_import_names() -> None:
    config = _load_importlinter_config()
    configured = frozenset(config["root_packages"])
    assert configured == EXPECTED_ROOT_PACKAGES
    assert len(configured) == 16


def test_layer_and_independence_contracts_configured() -> None:
    config = _load_importlinter_config()
    contracts = config["contracts"]
    names = {c["name"] for c in contracts}
    assert LAYER_CONTRACT_NAME in names
    assert INDEPENDENCE_CONTRACT_NAME in names

    layers = next(c for c in contracts if c["name"] == LAYER_CONTRACT_NAME)
    assert layers["type"] == "layers"
    assert "iris_engine" in layers["layers"][-1]
    assert "iris_api" in layers["layers"][0]

    independence = next(c for c in contracts if c["name"] == INDEPENDENCE_CONTRACT_NAME)
    assert independence["type"] == "independence"
    assert frozenset(independence["modules"]) == frozenset(
        name
        for name in EXPECTED_ROOT_PACKAGES
        if name.startswith("iris_ocr_") or name.startswith("iris_llm_")
    )


@pytest.mark.slow
def test_lint_imports_succeeds_on_scaffold() -> None:
    result = subprocess.run(
        ["uv", "run", "lint-imports"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"lint-imports failed (exit {result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
