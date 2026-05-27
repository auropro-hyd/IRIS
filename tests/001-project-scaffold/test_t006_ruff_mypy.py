"""T006 acceptance tests for ruff and mypy configuration.

Fast tests inspect pyproject.toml for the required sections and values.
Slow tests execute ``make lint`` and ``make typecheck`` and assert exit zero.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"

STRICT_MODULES = [
    "iris_engine",
    "iris_ocr_adi",
    "iris_ocr_datalab",
    "iris_ocr_paddleocr",
    "iris_ocr_local",
    "iris_llm_azure_openai",
    "iris_llm_openai",
    "iris_llm_anthropic",
    "iris_llm_local",
]


def _load_pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text())


# ── ruff ─────────────────────────────────────────────────────────────────────


def test_ruff_section_exists() -> None:
    cfg = _load_pyproject()
    assert "ruff" in cfg.get("tool", {}), "[tool.ruff] section missing from pyproject.toml"


def test_ruff_line_length_is_100() -> None:
    cfg = _load_pyproject()
    assert cfg["tool"]["ruff"].get("line-length") == 100, (
        "[tool.ruff] line-length should be 100"
    )


def test_ruff_target_version_is_py312() -> None:
    cfg = _load_pyproject()
    assert cfg["tool"]["ruff"].get("target-version") == "py312", (
        "[tool.ruff] target-version should be py312"
    )


def test_ruff_lint_selects_core_rules() -> None:
    cfg = _load_pyproject()
    selected = set(cfg["tool"]["ruff"]["lint"].get("select", []))
    required = {"E", "F", "I", "UP", "B"}
    missing = sorted(required - selected)
    assert not missing, f"[tool.ruff.lint] select is missing rule sets: {missing}"


def test_ruff_importable() -> None:
    import importlib.util

    assert importlib.util.find_spec("ruff") is not None, (
        "ruff is not installed in the active environment"
    )


# ── mypy ─────────────────────────────────────────────────────────────────────


def test_mypy_section_exists() -> None:
    cfg = _load_pyproject()
    assert "mypy" in cfg.get("tool", {}), "[tool.mypy] section missing from pyproject.toml"


def test_mypy_python_version_is_312() -> None:
    cfg = _load_pyproject()
    assert cfg["tool"]["mypy"].get("python_version") == "3.12", (
        "[tool.mypy] python_version should be '3.12'"
    )


def test_mypy_strict_overrides_cover_engine_and_adapters() -> None:
    cfg = _load_pyproject()
    overrides = cfg["tool"]["mypy"].get("overrides", [])
    strict_modules: set[str] = set()
    for override in overrides:
        if override.get("strict"):
            for mod in override.get("module", []):
                strict_modules.add(mod)
    missing = sorted(m for m in STRICT_MODULES if m not in strict_modules)
    assert not missing, (
        f"mypy strict overrides missing for: {missing}"
    )


def test_mypy_tests_override_relaxes_errors() -> None:
    cfg = _load_pyproject()
    overrides = cfg["tool"]["mypy"].get("overrides", [])
    relaxed = any(
        "tests" in str(override.get("module", ""))
        for override in overrides
        if override.get("ignore_errors")
    )
    assert relaxed, "No mypy override found that relaxes error checking for tests.*"


def test_mypy_importable() -> None:
    import importlib.util

    assert importlib.util.find_spec("mypy") is not None, (
        "mypy is not installed in the active environment"
    )


# ── make targets ─────────────────────────────────────────────────────────────


@pytest.mark.slow
def test_make_lint_exits_zero() -> None:
    if shutil.which("make") is None:
        pytest.skip("make not available on this host")
    result = subprocess.run(
        ["make", "lint"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"make lint exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.mark.slow
def test_make_typecheck_exits_zero() -> None:
    if shutil.which("make") is None:
        pytest.skip("make not available on this host")
    result = subprocess.run(
        ["make", "typecheck"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"make typecheck exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
