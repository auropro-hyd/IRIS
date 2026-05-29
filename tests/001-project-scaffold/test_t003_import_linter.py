"""
T003 acceptance: import-linter enforces IRIS layer boundaries on workspace packages.

Default (config only):
  uv run pytest tests/001-project-scaffold/test_t003_import_linter.py -v

Including lint-imports subprocess (slow):
  uv run pytest tests/001-project-scaffold/test_t003_import_linter.py -v -m slow
"""

from __future__ import annotations

import subprocess
import tomllib
from typing import Any

import pytest
from test_t001_workspace import MEMBER_SRC_PACKAGES, REPO_ROOT

EXPECTED_ROOT_PACKAGES = frozenset(MEMBER_SRC_PACKAGES.values())

LAYER_CONTRACT_NAME = "IRIS apps, packages, adapters, engine"
INDEPENDENCE_CONTRACT_NAME = "Adapters do not depend on each other"
FORBIDDEN_CONTRACT_NAME = "Mid-packages do not import concrete adapters"

EXPECTED_MID_PACKAGES = frozenset({"iris_agents", "iris_data", "iris_config", "iris_observability"})

# Must match [[tool.importlinter.contracts]] layers in root pyproject.toml exactly.
EXPECTED_LAYERS: tuple[str, ...] = (
    "iris_api | iris_worker | iris_cli",
    "iris_agents | iris_data | iris_config | iris_observability",
    (
        "iris_ocr_adi | iris_ocr_datalab | iris_ocr_paddleocr | iris_ocr_local | "
        "iris_llm_azure_openai | iris_llm_openai | iris_llm_anthropic | iris_llm_local"
    ),
    "iris_engine",
)

EXPECTED_ADAPTER_MODULES = frozenset(
    name
    for name in EXPECTED_ROOT_PACKAGES
    if name.startswith("iris_ocr_") or name.startswith("iris_llm_")
)


def _layer_modules(layer: str) -> frozenset[str]:
    return frozenset(part.strip() for part in layer.split("|"))


def _load_importlinter_config() -> dict[str, Any]:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["tool"]["importlinter"]


def test_root_packages_match_workspace_import_names() -> None:
    config = _load_importlinter_config()
    configured = frozenset(config["root_packages"])
    assert configured == EXPECTED_ROOT_PACKAGES
    assert len(configured) == 16


def test_import_linter_contracts_configured() -> None:
    config = _load_importlinter_config()
    contracts = config["contracts"]
    names = {c["name"] for c in contracts}
    assert LAYER_CONTRACT_NAME in names
    assert INDEPENDENCE_CONTRACT_NAME in names
    assert FORBIDDEN_CONTRACT_NAME in names

    layers = next(c for c in contracts if c["name"] == LAYER_CONTRACT_NAME)
    assert layers["type"] == "layers"
    configured_layers = layers["layers"]
    assert configured_layers == list(EXPECTED_LAYERS)
    assert _layer_modules(configured_layers[0]) == frozenset(
        {"iris_api", "iris_worker", "iris_cli"}
    )
    assert _layer_modules(configured_layers[1]) == frozenset(
        {"iris_agents", "iris_data", "iris_config", "iris_observability"}
    )
    assert _layer_modules(configured_layers[2]) == EXPECTED_ADAPTER_MODULES
    assert configured_layers[3] == "iris_engine"
    assert _layer_modules(configured_layers[3]) == frozenset({"iris_engine"})

    independence = next(c for c in contracts if c["name"] == INDEPENDENCE_CONTRACT_NAME)
    assert independence["type"] == "independence"
    assert frozenset(independence["modules"]) == EXPECTED_ADAPTER_MODULES

    forbidden = next(c for c in contracts if c["name"] == FORBIDDEN_CONTRACT_NAME)
    assert forbidden["type"] == "forbidden"
    assert frozenset(forbidden["source_modules"]) == EXPECTED_MID_PACKAGES
    assert frozenset(forbidden["forbidden_modules"]) == EXPECTED_ADAPTER_MODULES


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
