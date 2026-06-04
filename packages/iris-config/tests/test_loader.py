"""Unit tests for iris_config.loader (T025)."""

import shutil
from pathlib import Path

import pytest
from iris_config.exceptions import ConfigLoadError
from iris_config.loader import ProductConfig, load_bundle, load_products

FIXTURES = Path(__file__).parent / "fixtures"
VALID_BUNDLE = FIXTURES / "valid-bundle"
INVALID_BUNDLES = FIXTURES / "invalid-bundles"


# ── happy path ────────────────────────────────────────────────────────────────


def test_load_bundle_returns_product_config() -> None:
    pc = load_bundle(VALID_BUNDLE, "valid-bundle")
    assert isinstance(pc, ProductConfig)


def test_load_bundle_slug_is_preserved() -> None:
    pc = load_bundle(VALID_BUNDLE, "valid-bundle")
    assert pc.slug == "valid-bundle"


def test_load_bundle_region_matches_yaml() -> None:
    pc = load_bundle(VALID_BUNDLE, "valid-bundle")
    assert pc.schema.region == "in"


def test_load_bundle_retention_days() -> None:
    pc = load_bundle(VALID_BUNDLE, "valid-bundle")
    assert pc.schema.retention_days == 2555


def test_load_bundle_adapters() -> None:
    pc = load_bundle(VALID_BUNDLE, "valid-bundle")
    assert pc.schema.adapters.ocr == "paddleocr"
    assert pc.schema.adapters.llm == "azure-openai"


def test_load_bundle_taxonomy_has_two_document_types() -> None:
    pc = load_bundle(VALID_BUNDLE, "valid-bundle")
    assert len(pc.schema.taxonomy.document_types) == 2


def test_load_bundle_required_documents() -> None:
    pc = load_bundle(VALID_BUNDLE, "valid-bundle")
    assert "police_report" in pc.schema.taxonomy.required_documents


def test_load_bundle_extraction_fields() -> None:
    pc = load_bundle(VALID_BUNDLE, "valid-bundle")
    field_names = [f.name for f in pc.schema.extraction.fields]
    assert "date_of_loss" in field_names
    assert "vehicle_plate" in field_names


def test_load_bundle_prompts() -> None:
    pc = load_bundle(VALID_BUNDLE, "valid-bundle")
    assert pc.schema.prompts.classify.path == "prompts/classify.j2"
    assert "taxonomy" in pc.schema.prompts.classify.variables


def test_load_products_finds_valid_bundle(tmp_path: Path) -> None:
    dest = tmp_path / "auto" / "in"
    dest.mkdir(parents=True)
    shutil.copytree(VALID_BUNDLE, dest, dirs_exist_ok=True)
    registry = load_products(tmp_path)
    assert "auto/in" in registry


def test_load_products_returns_product_config_instances(tmp_path: Path) -> None:
    dest = tmp_path / "lob" / "in"
    dest.mkdir(parents=True)
    shutil.copytree(VALID_BUNDLE, dest, dirs_exist_ok=True)
    registry = load_products(tmp_path)
    assert isinstance(registry["lob/in"], ProductConfig)


def test_load_products_multiple_bundles(tmp_path: Path) -> None:
    for slug in ("auto/in", "auto/us"):
        dest = tmp_path / slug
        dest.mkdir(parents=True)
        shutil.copytree(VALID_BUNDLE, dest, dirs_exist_ok=True)
    registry = load_products(tmp_path)
    assert set(registry) == {"auto/in", "auto/us"}


# ── missing required file ─────────────────────────────────────────────────────


def test_missing_taxonomy_raises_config_load_error() -> None:
    with pytest.raises(ConfigLoadError):
        load_bundle(INVALID_BUNDLES / "missing-taxonomy", "missing-taxonomy")


def test_missing_taxonomy_error_slug() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "missing-taxonomy", "missing-taxonomy")
    assert exc_info.value.slug == "missing-taxonomy"


def test_missing_taxonomy_error_names_taxonomy_file() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "missing-taxonomy", "missing-taxonomy")
    assert "taxonomy.yaml" in str(exc_info.value.file)


def test_missing_taxonomy_error_message_explains_problem() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "missing-taxonomy", "missing-taxonomy")
    assert "not found" in str(exc_info.value)


# ── schema validation failures ────────────────────────────────────────────────


def test_unknown_ocr_adapter_raises_config_load_error() -> None:
    with pytest.raises(ConfigLoadError):
        load_bundle(INVALID_BUNDLES / "unknown-ocr-adapter", "unknown-ocr-adapter")


def test_unknown_ocr_adapter_error_names_product_file() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "unknown-ocr-adapter", "unknown-ocr-adapter")
    assert "product.yaml" in str(exc_info.value.file)


def test_unknown_ocr_adapter_error_names_bundle() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "unknown-ocr-adapter", "unknown-ocr-adapter")
    assert "unknown-ocr-adapter" in str(exc_info.value)


def test_duplicate_doc_type_raises_config_load_error() -> None:
    with pytest.raises(ConfigLoadError):
        load_bundle(INVALID_BUNDLES / "duplicate-doc-type", "duplicate-doc-type")


def test_duplicate_doc_type_error_names_taxonomy_file() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "duplicate-doc-type", "duplicate-doc-type")
    assert "taxonomy.yaml" in str(exc_info.value.file)


def test_duplicate_doc_type_error_names_bundle() -> None:
    with pytest.raises(ConfigLoadError) as exc_info:
        load_bundle(INVALID_BUNDLES / "duplicate-doc-type", "duplicate-doc-type")
    assert "duplicate-doc-type" in str(exc_info.value)
