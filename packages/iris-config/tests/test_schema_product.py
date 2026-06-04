"""Unit tests for iris_config.schema.product and iris_config.schema.adapters (T021, T022)."""

import pytest
from iris_config.schema.adapters import AdaptersSchema
from iris_config.schema.extraction import ExtractionSchema, FieldSchema
from iris_config.schema.product import ProductSchema
from iris_config.schema.prompts import PromptSchema, PromptTemplateSchema
from iris_config.schema.taxonomy import DocumentTypeSchema, TaxonomySchema
from pydantic_core import ValidationError

_VALID_ADAPTERS = AdaptersSchema(ocr="paddleocr", llm="azure-openai")

_VALID_TAXONOMY = TaxonomySchema(
    document_types=[
        DocumentTypeSchema(
            name="police_report",
            label="Police Report",
            description="Official police report filed for the incident",
        )
    ],
    required_documents=["police_report"],
)

_VALID_EXTRACTION = ExtractionSchema(
    fields=[
        FieldSchema(
            name="date_of_loss",
            label="Date of Loss",
            type="date",
            required=True,
            description="Date of loss",
        ),
    ]
)

_VALID_PROMPTS = PromptSchema(
    classify=PromptTemplateSchema(path="prompts/classify.j2", variables=["taxonomy", "ocr_text"]),
    extract=PromptTemplateSchema(path="prompts/extract.j2", variables=["fields", "ocr_text"]),
    summarize=PromptTemplateSchema(path="prompts/summarize.j2", variables=["claim_data"]),
)


def _valid_product() -> ProductSchema:
    return ProductSchema(
        region="in",
        retention_days=2555,
        adapters=_VALID_ADAPTERS,
        taxonomy=_VALID_TAXONOMY,
        extraction=_VALID_EXTRACTION,
        prompts=_VALID_PROMPTS,
    )


# ── T021: ProductSchema round-trip ────────────────────────────────────────────


def test_valid_product_schema_loads() -> None:
    product = _valid_product()
    assert product.region == "in"
    assert product.retention_days == 2555


def test_product_schema_round_trips() -> None:
    product = _valid_product()
    assert ProductSchema.model_validate(product.model_dump()) == product


def test_retention_days_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ProductSchema(
            region="in",
            retention_days=0,
            adapters=_VALID_ADAPTERS,
            taxonomy=_VALID_TAXONOMY,
            extraction=_VALID_EXTRACTION,
            prompts=_VALID_PROMPTS,
        )


def test_empty_taxonomy_document_types_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        ProductSchema(
            region="in",
            retention_days=2555,
            adapters=_VALID_ADAPTERS,
            taxonomy=TaxonomySchema(document_types=[], required_documents=[]),
            extraction=_VALID_EXTRACTION,
            prompts=_VALID_PROMPTS,
        )


def test_unknown_field_on_product_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ProductSchema.model_validate(
            {
                "region": "in",
                "retention_days": 2555,
                "adapters": {"ocr": "paddleocr", "llm": "azure-openai"},
                "taxonomy": {
                    "document_types": [
                        {
                            "name": "police_report",
                            "label": "Police Report",
                            "description": "...",
                        }
                    ],
                    "required_documents": [],
                },
                "extraction": {},
                "prompts": {},
                "unknown_key": "value",
            }
        )


# ── T022: AdaptersSchema Literal validation ───────────────────────────────────


def test_valid_ocr_adapters_load() -> None:
    for ocr in ("adi", "datalab", "paddleocr", "local"):
        adapter = AdaptersSchema(ocr=ocr, llm="openai")  # type: ignore[arg-type]
        assert adapter.ocr == ocr


def test_valid_llm_adapters_load() -> None:
    for llm in ("azure-openai", "openai", "anthropic", "local"):
        adapter = AdaptersSchema(ocr="local", llm=llm)  # type: ignore[arg-type]
        assert adapter.llm == llm


def test_invalid_ocr_adapter_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        AdaptersSchema(ocr="paddel-ocr", llm="azure-openai")


def test_invalid_ocr_error_message_lists_valid_options() -> None:
    with pytest.raises(ValidationError, match="adi|datalab|paddleocr|local"):
        AdaptersSchema(ocr="paddel-ocr", llm="azure-openai")


def test_invalid_llm_adapter_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        AdaptersSchema(ocr="paddleocr", llm="gpt-4")


def test_unknown_field_on_adapters_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        AdaptersSchema.model_validate({"ocr": "paddleocr", "llm": "openai", "blob": "s3"})
