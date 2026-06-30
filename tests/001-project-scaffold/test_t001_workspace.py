"""
Scaffold layout and T001 uv workspace acceptance (plan 001 proposed file layout).

Default run (fast, no uv sync):
  uv run pytest tests/001-project-scaffold/test_t001_workspace.py -v

Full T001 acceptance including uv sync (slow):
  uv run pytest tests/001-project-scaffold/test_t001_workspace.py -v -m slow
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _venv_python_executable(repo_root: Path) -> Path:
    """Return the venv interpreter path (Unix bin/python, Windows Scripts/python.exe)."""
    if sys.platform == "win32":
        return repo_root / ".venv" / "Scripts" / "python.exe"
    return repo_root / ".venv" / "bin" / "python"


# uv workspace members (apps/workbench is pnpm, not listed here)
EXPECTED_WORKSPACE_MEMBERS: frozenset[str] = frozenset(
    {
        "apps/api",
        "apps/worker",
        "packages/iris-engine",
        "packages/iris-agents",
        "packages/iris-data",
        "packages/iris-config",
        "packages/iris-observability",
        "packages/iris-adapters/ocr-adi",
        "packages/iris-adapters/ocr-datalab",
        "packages/iris-adapters/ocr-paddleocr",
        "packages/iris-adapters/ocr-local",
        "packages/iris-adapters/llm-shared",
        "packages/iris-adapters/llm-azure-openai",
        "packages/iris-adapters/llm-openai",
        "packages/iris-adapters/llm-anthropic",
        "packages/iris-adapters/llm-local",
        "tools/iris-cli",
    }
)

# member path -> import package directory under src/ (plan: src/<namespace>/)
MEMBER_SRC_PACKAGES: dict[str, str] = {
    "apps/api": "iris_api",
    "apps/worker": "iris_worker",
    "packages/iris-engine": "iris_engine",
    "packages/iris-agents": "iris_agents",
    "packages/iris-data": "iris_data",
    "packages/iris-config": "iris_config",
    "packages/iris-observability": "iris_observability",
    "packages/iris-adapters/ocr-adi": "iris_ocr_adi",
    "packages/iris-adapters/ocr-datalab": "iris_ocr_datalab",
    "packages/iris-adapters/ocr-paddleocr": "iris_ocr_paddleocr",
    "packages/iris-adapters/ocr-local": "iris_ocr_local",
    "packages/iris-adapters/llm-shared": "iris_adapter_llm_shared",
    "packages/iris-adapters/llm-azure-openai": "iris_adapter_llm_azure_openai",
    "packages/iris-adapters/llm-openai": "iris_llm_openai",
    "packages/iris-adapters/llm-anthropic": "iris_llm_anthropic",
    "packages/iris-adapters/llm-local": "iris_llm_local",
    "tools/iris-cli": "iris_cli",
}

# Directories from plan 001 (workstream tests mirror tasks/ naming)
EXPECTED_DIRECTORIES: tuple[str, ...] = (
    "apps/api",
    "apps/worker",
    "apps/workbench",
    "packages/iris-engine",
    "packages/iris-agents",
    "packages/iris-data",
    "packages/iris-config",
    "packages/iris-observability",
    "packages/iris-adapters",
    "tools/iris-cli",
    "tests/001-project-scaffold",
    "tests/contract",
    "tests/integration",
    "tests/e2e",
    "config/products",
    "docker",
    "docs",
    "tasks",
    "scripts",
    ".github",
)

# Root files introduced by workstream 001 (land in later tasks; not asserted here)
PLANNED_ROOT_FILES: tuple[str, ...] = (
    "compose.dev.yaml",
    "Makefile",
    ".env.example",
)


def _load_root_pyproject() -> dict[str, object]:
    pyproject_path = REPO_ROOT / "pyproject.toml"
    assert pyproject_path.is_file(), "root pyproject.toml is missing"
    with pyproject_path.open("rb") as handle:
        return tomllib.load(handle)


def _resolve_workspace_members(members: list[object]) -> set[str]:
    configured: set[str] = set()
    for entry in members:
        assert isinstance(entry, str)
        if entry.endswith("/*"):
            parent = REPO_ROOT / entry[:-2]
            for child in sorted(parent.iterdir()):
                if child.is_dir() and (child / "pyproject.toml").is_file():
                    configured.add(str(child.relative_to(REPO_ROOT)).replace("\\", "/"))
        else:
            configured.add(entry)
    return configured


def test_workspace_lists_every_member() -> None:
    data = _load_root_pyproject()
    workspace = data.get("tool", {})
    assert isinstance(workspace, dict)
    uv_table = workspace.get("uv", {})
    assert isinstance(uv_table, dict)
    ws_table = uv_table.get("workspace", {})
    assert isinstance(ws_table, dict)
    members = ws_table.get("members", [])
    assert isinstance(members, list)
    assert members, "tool.uv.workspace.members must not be empty"

    configured = _resolve_workspace_members(members)
    missing = EXPECTED_WORKSPACE_MEMBERS - configured
    extra = configured - EXPECTED_WORKSPACE_MEMBERS
    assert not missing, f"workspace members missing from pyproject.toml: {sorted(missing)}"
    assert not extra, f"unexpected workspace members in pyproject.toml: {sorted(extra)}"


def test_each_workspace_member_has_pyproject() -> None:
    for member in sorted(EXPECTED_WORKSPACE_MEMBERS):
        pyproject = REPO_ROOT / member / "pyproject.toml"
        assert pyproject.is_file(), f"{member}/pyproject.toml is missing"


def test_workbench_is_not_a_uv_member() -> None:
    data = _load_root_pyproject()
    workspace = data.get("tool", {})
    assert isinstance(workspace, dict)
    uv_table = workspace.get("uv", {})
    assert isinstance(uv_table, dict)
    ws_table = uv_table.get("workspace", {})
    assert isinstance(ws_table, dict)
    members = ws_table.get("members", [])
    assert isinstance(members, list)
    configured = _resolve_workspace_members(members)
    assert "apps/workbench" not in configured


def test_python_members_have_src_namespace() -> None:
    assert set(MEMBER_SRC_PACKAGES) == EXPECTED_WORKSPACE_MEMBERS
    for member, package in sorted(MEMBER_SRC_PACKAGES.items()):
        package_dir = REPO_ROOT / member / "src" / package
        init_py = package_dir / "__init__.py"
        assert init_py.is_file(), f"{member} must expose src/{package}/__init__.py"


def test_workbench_layout() -> None:
    workbench = REPO_ROOT / "apps/workbench"
    assert workbench.is_dir()
    assert (workbench / "package.json").is_file()
    assert (workbench / "src").is_dir()
    assert not (workbench / "pyproject.toml").exists()


def test_plan_directories_exist() -> None:
    for relative in EXPECTED_DIRECTORIES:
        path = REPO_ROOT / relative
        assert path.exists(), f"planned directory missing: {relative}/"


def test_shared_test_suite_directories_exist() -> None:
    for name in ("contract", "integration", "e2e"):
        path = REPO_ROOT / "tests" / name
        assert path.is_dir(), f"tests/{name}/ is required by plan 001"


def test_config_and_docker_layout() -> None:
    assert (REPO_ROOT / "config" / "products").is_dir()
    assert (REPO_ROOT / "docker" / "api.Dockerfile").is_file()
    assert (REPO_ROOT / "docker" / "worker.Dockerfile").is_file()


def test_root_workspace_files_exist() -> None:
    assert (REPO_ROOT / "pyproject.toml").is_file()
    assert (REPO_ROOT / ".python-version").is_file()


@pytest.mark.slow
def test_uv_sync_all_packages_creates_venv() -> None:
    result = subprocess.run(
        ["uv", "sync", "--all-packages"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    venv_python = _venv_python_executable(REPO_ROOT)
    assert venv_python.is_file(), f".venv was not created by uv sync (expected {venv_python})"
    version = subprocess.run(
        [str(venv_python), "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "3.12" in version.stdout or "3.13" in version.stdout or "3.14" in version.stdout
