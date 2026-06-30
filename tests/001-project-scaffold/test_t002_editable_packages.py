"""
T002 acceptance: workspace members install editable and import as namespaces.

Default (imports only):
  uv run pytest tests/001-project-scaffold/test_t002_editable_packages.py -v

Including uv pip list check (slow):
  uv run pytest tests/001-project-scaffold/test_t002_editable_packages.py -v -m slow
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest
from test_t001_workspace import EXPECTED_WORKSPACE_MEMBERS, MEMBER_SRC_PACKAGES, REPO_ROOT

# pyproject [project].name per member (PEP 503 distribution name)
MEMBER_DISTRIBUTION_NAMES: dict[str, str] = {
    "apps/api": "iris-api",
    "apps/worker": "iris-worker",
    "packages/iris-engine": "iris-engine",
    "packages/iris-agents": "iris-agents",
    "packages/iris-data": "iris-data",
    "packages/iris-config": "iris-config",
    "packages/iris-observability": "iris-observability",
    "packages/iris-adapters/ocr-adi": "iris-ocr-adi",
    "packages/iris-adapters/ocr-datalab": "iris-ocr-datalab",
    "packages/iris-adapters/ocr-paddleocr": "iris-ocr-paddleocr",
    "packages/iris-adapters/ocr-local": "iris-ocr-local",
    "packages/iris-adapters/llm-shared": "iris-adapter-llm-shared",
    "packages/iris-adapters/llm-azure-openai": "iris-adapter-llm-azure-openai",
    "packages/iris-adapters/llm-openai": "iris-adapter-llm-openai",
    "packages/iris-adapters/llm-anthropic": "iris-adapter-llm-anthropic",
    "packages/iris-adapters/llm-local": "iris-adapter-llm-local",
    "tools/iris-cli": "iris-cli",
}


def _uv_pip_list() -> str:
    result = subprocess.run(
        ["uv", "pip", "list"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"uv pip list failed (exit {result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result.stdout


@pytest.mark.slow
def test_uv_pip_list_shows_all_members_editable() -> None:
    assert set(MEMBER_DISTRIBUTION_NAMES) == EXPECTED_WORKSPACE_MEMBERS
    listing = _uv_pip_list()
    for member, dist_name in sorted(MEMBER_DISTRIBUTION_NAMES.items()):
        assert dist_name in listing, f"{dist_name} missing from uv pip list"
        member_root = str((REPO_ROOT / member).resolve())
        assert (
            member_root in listing
        ), f"{dist_name} is not installed in editable mode (expected path {member_root})"


def test_each_namespace_imports() -> None:
    assert set(MEMBER_SRC_PACKAGES) == EXPECTED_WORKSPACE_MEMBERS
    for member, package in sorted(MEMBER_SRC_PACKAGES.items()):
        module = importlib.import_module(package)
        expected_src = (REPO_ROOT / member / "src" / package).resolve()
        module_file = module.__file__
        assert module_file is not None, f"{package} has no __file__"
        module_path = Path(module_file).resolve().parent
        assert (
            module_path == expected_src
        ), f"import {package} resolved to {module_path}, expected {expected_src}"
