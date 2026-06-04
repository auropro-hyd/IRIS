"""Integration tests for `iris config validate` (T027).

Exercises the boundary between iris_cli (Click command) and iris_config
(loader + validator). Uses Click's CliRunner — no subprocess, no live services.
"""

from pathlib import Path

from click.testing import CliRunner
from iris_cli import iris

REPO_ROOT = Path(__file__).parent.parent.parent
FIXTURES = REPO_ROOT / "packages/iris-config/tests/fixtures"
VALID_BUNDLE = FIXTURES / "valid-bundle"
INVALID_BUNDLES = FIXTURES / "invalid-bundles"
PRODUCTS_ROOT = REPO_ROOT / "config" / "products"


def _run(*args: str) -> CliRunner:
    return CliRunner().invoke(iris, list(args))  # type: ignore[return-value]


# ── exit codes ────────────────────────────────────────────────────────────────


def test_valid_bundle_exits_zero() -> None:
    result = _run("config", "validate", str(VALID_BUNDLE))
    assert result.exit_code == 0


def test_unknown_ocr_adapter_exits_one() -> None:
    result = _run("config", "validate", str(INVALID_BUNDLES / "unknown-ocr-adapter"))
    assert result.exit_code == 1


def test_duplicate_doc_type_exits_one() -> None:
    result = _run("config", "validate", str(INVALID_BUNDLES / "duplicate-doc-type"))
    assert result.exit_code == 1


def test_missing_taxonomy_exits_one() -> None:
    result = _run("config", "validate", str(INVALID_BUNDLES / "missing-taxonomy"))
    assert result.exit_code == 1


def test_products_root_exits_zero() -> None:
    result = _run("config", "validate", str(PRODUCTS_ROOT))
    assert result.exit_code == 0


# ── output ────────────────────────────────────────────────────────────────────


def test_valid_bundle_prints_ok() -> None:
    result = _run("config", "validate", str(VALID_BUNDLE))
    assert "OK" in result.output


def test_invalid_bundle_error_message_contains_invalid_value() -> None:
    result = _run("config", "validate", str(INVALID_BUNDLES / "unknown-ocr-adapter"))
    assert result.exit_code == 1
    assert "paddel-ocr" in result.output


def test_products_root_prints_slug() -> None:
    result = _run("config", "validate", str(PRODUCTS_ROOT))
    assert "commercial-auto-claims/in" in result.output
