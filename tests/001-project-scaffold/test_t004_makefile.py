"""T004 acceptance tests for the root Makefile.

Fast tests verify the Makefile defines the nine targets listed in
``tasks/001-project-scaffold/tasks.md`` and that each has a recipe. Slow
tests execute every target except ``install`` (covered by T001 via
``uv sync --all-packages``) and ``test`` (would recurse into pytest) and
``lint`` (already exercised by T003's slow check) and assert exit zero.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"

REQUIRED_TARGETS = (
    "install",
    "dev",
    "up",
    "down",
    "lint",
    "typecheck",
    "test",
    "test-cov",
    "clean",
)


def _phony_targets(text: str) -> set[str]:
    targets: set[str] = set()
    for line in text.splitlines():
        if line.startswith(".PHONY:"):
            for word in line.split()[1:]:
                targets.add(word)
    return targets


def _target_recipe_lines(text: str, target: str) -> list[str]:
    pattern = re.compile(
        rf"^{re.escape(target)}\s*:.*?\n((?:^\t.*\n?)+)",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return []
    return [line for line in match.group(1).splitlines() if line.strip()]


def test_makefile_exists() -> None:
    assert MAKEFILE.is_file(), f"expected Makefile at {MAKEFILE}"


def test_makefile_declares_required_phony_targets() -> None:
    phony = _phony_targets(MAKEFILE.read_text())
    missing = sorted(set(REQUIRED_TARGETS) - phony)
    assert not missing, f".PHONY targets missing from Makefile: {missing}"


@pytest.mark.parametrize("target", REQUIRED_TARGETS)
def test_target_has_recipe(target: str) -> None:
    text = MAKEFILE.read_text()
    assert _target_recipe_lines(text, target), (
        f"target {target!r} has no recipe in Makefile"
    )


@pytest.mark.parametrize("target", REQUIRED_TARGETS)
def test_target_dry_runs_zero(target: str) -> None:
    """`make -n <target>` exits zero so the recipe is syntactically valid."""
    if shutil.which("make") is None:
        pytest.skip("make not available on this host")
    result = subprocess.run(
        ["make", "-n", target],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"make -n {target} exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    "target",
    ["dev", "up", "down", "typecheck", "test-cov", "clean"],
)
def test_guarded_target_exits_zero(target: str) -> None:
    """Guarded or placeholder targets execute and exit zero on a fresh clone."""
    if shutil.which("make") is None:
        pytest.skip("make not available on this host")
    result = subprocess.run(
        ["make", target],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"make {target} exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_lint_recipe_calls_lint_imports() -> None:
    """make lint must invoke import-linter (the only linter wired in T004)."""
    text = MAKEFILE.read_text()
    recipe = "\n".join(_target_recipe_lines(text, "lint"))
    assert "lint-imports" in recipe, f"lint recipe does not call lint-imports:\n{recipe}"


def test_test_recipe_calls_pytest() -> None:
    text = MAKEFILE.read_text()
    recipe = "\n".join(_target_recipe_lines(text, "test"))
    assert "pytest" in recipe, f"test recipe does not call pytest:\n{recipe}"


def test_install_recipe_calls_uv_sync() -> None:
    text = MAKEFILE.read_text()
    recipe = "\n".join(_target_recipe_lines(text, "install"))
    assert "sync" in recipe, (
        f"install recipe does not call uv sync:\n{recipe}"
    )
