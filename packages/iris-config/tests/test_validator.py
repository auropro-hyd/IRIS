"""Unit tests for iris_config.validator (T026).

Acceptance: each of the three invalid-bundles/* fixtures produces an error
message containing bundle slug, file path, field path, and invalid value.
"""

from pathlib import Path

import pytest
from iris_config.exceptions import ConfigLoadError
from iris_config.loader import load_bundle

INVALID_BUNDLES = Path(__file__).parent / "fixtures" / "invalid-bundles"


# ── unknown-ocr-adapter: all four elements present ───────────────────────────


def test_ocr_adapter_error_contains_slug() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "unknown-ocr-adapter", "unknown-ocr-adapter")
    assert "unknown-ocr-adapter" in str(exc_info.value)


def test_ocr_adapter_error_contains_file_path() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "unknown-ocr-adapter", "unknown-ocr-adapter")
    assert "product.yaml" in str(exc_info.value)


def test_ocr_adapter_error_contains_field_path() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "unknown-ocr-adapter", "unknown-ocr-adapter")
    msg = str(exc_info.value)
    assert "adapters" in msg
    assert "ocr" in msg


def test_ocr_adapter_error_contains_invalid_value() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "unknown-ocr-adapter", "unknown-ocr-adapter")
    assert "paddel-ocr" in str(exc_info.value)


def test_ocr_adapter_error_contains_valid_options() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "unknown-ocr-adapter", "unknown-ocr-adapter")
    msg = str(exc_info.value)
    assert "paddleocr" in msg or "adi" in msg or "datalab" in msg


# ── duplicate-doc-type: all four elements present ────────────────────────────


def test_duplicate_doc_type_error_contains_slug() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "duplicate-doc-type", "duplicate-doc-type")
    assert "duplicate-doc-type" in str(exc_info.value)


def test_duplicate_doc_type_error_contains_file_path() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "duplicate-doc-type", "duplicate-doc-type")
    assert "taxonomy.yaml" in str(exc_info.value)


def test_duplicate_doc_type_error_contains_field_path() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "duplicate-doc-type", "duplicate-doc-type")
    assert "taxonomy" in str(exc_info.value)


def test_duplicate_doc_type_error_mentions_duplicate_name() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "duplicate-doc-type", "duplicate-doc-type")
    assert "police_report" in str(exc_info.value)


# ── missing-taxonomy: file-level error has all required context ───────────────


def test_missing_taxonomy_error_contains_slug() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "missing-taxonomy", "missing-taxonomy")
    assert "missing-taxonomy" in str(exc_info.value)


def test_missing_taxonomy_error_contains_file_path() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "missing-taxonomy", "missing-taxonomy")
    assert "taxonomy.yaml" in str(exc_info.value)


def test_missing_taxonomy_error_is_config_load_error_instance() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "missing-taxonomy", "missing-taxonomy")
    assert isinstance(exc_info.value, ConfigLoadError)
    assert exc_info.value.slug == "missing-taxonomy"
