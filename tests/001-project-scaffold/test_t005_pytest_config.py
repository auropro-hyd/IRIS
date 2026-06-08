"""T005 acceptance tests for pytest markers and coverage configuration.

Fast tests inspect pyproject.toml for the required marker declarations,
default-exclusion addopts, and coverage sections. A slow test runs
``make test-cov`` and asserts that ``htmlcov/index.html`` is produced.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"

REQUIRED_MARKERS = ("contract", "integration", "e2e", "slow")


def _load_pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text())


def test_pyproject_has_required_markers() -> None:
    cfg = _load_pyproject()
    declared = cfg["tool"]["pytest"]["ini_options"]["markers"]
    prefixes = {m.split(":")[0].strip() for m in declared}
    missing = sorted(set(REQUIRED_MARKERS) - prefixes)
    assert not missing, f"pytest markers missing from pyproject.toml: {missing}"


def test_addopts_excludes_e2e_by_default() -> None:
    cfg = _load_pyproject()
    addopts = " ".join(cfg["tool"]["pytest"]["ini_options"].get("addopts", []))
    assert "e2e" in addopts, f"addopts does not exclude e2e tests by default: {addopts!r}"


def test_addopts_excludes_slow_by_default() -> None:
    cfg = _load_pyproject()
    addopts = " ".join(cfg["tool"]["pytest"]["ini_options"].get("addopts", []))
    assert "slow" in addopts, f"addopts does not exclude slow tests by default: {addopts!r}"


def test_coverage_run_source_includes_iris_engine() -> None:
    cfg = _load_pyproject()
    source = cfg["tool"]["coverage"]["run"]["source"]
    assert (
        "iris_engine" in source
    ), f"[tool.coverage.run] source does not include iris_engine: {source}"


def test_coverage_run_branch_enabled() -> None:
    cfg = _load_pyproject()
    assert (
        cfg["tool"]["coverage"]["run"].get("branch") is True
    ), "[tool.coverage.run] branch is not set to true"


def test_coverage_report_fail_under_95() -> None:
    cfg = _load_pyproject()
    fail_under = cfg["tool"]["coverage"]["report"].get("fail_under")
    assert fail_under == 95, f"[tool.coverage.report] fail_under should be 95, got {fail_under}"


def test_coverage_html_directory_is_htmlcov() -> None:
    cfg = _load_pyproject()
    directory = cfg["tool"]["coverage"]["html"].get("directory")
    assert (
        directory == "htmlcov"
    ), f"[tool.coverage.html] directory should be 'htmlcov', got {directory!r}"


def test_pytest_cov_importable() -> None:
    import importlib.util

    assert (
        importlib.util.find_spec("pytest_cov") is not None
    ), "pytest-cov is not installed in the active environment"


@pytest.mark.slow
def test_make_test_cov_produces_html_report() -> None:
    """make test-cov must exit zero and write htmlcov/index.html."""
    if shutil.which("make") is None:
        pytest.skip("make not available on this host")
    htmlcov = REPO_ROOT / "htmlcov"
    result = subprocess.run(
        ["make", "test-cov"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"make test-cov exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert (htmlcov / "index.html").is_file(), f"htmlcov/index.html not produced under {htmlcov}"
