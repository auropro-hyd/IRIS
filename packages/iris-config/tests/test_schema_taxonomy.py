"""Unit tests for iris_config.schema.taxonomy (T020)."""

import pytest
from iris_config.schema.taxonomy import DocumentTypeSchema, TaxonomySchema
from pydantic import ValidationError

_VALID_DOC_TYPES: list[DocumentTypeSchema] = [
    DocumentTypeSchema(
        name="police_report",
        label="Police Report",
        description="Official police report filed for the incident",
    ),
    DocumentTypeSchema(
        name="vehicle_photos",
        label="Vehicle Photos",
        description="Photographs of vehicle damage",
    ),
]


def test_valid_taxonomy_loads() -> None:
    taxonomy = TaxonomySchema(
        document_types=_VALID_DOC_TYPES,
        required_documents=["police_report"],
    )
    assert len(taxonomy.document_types) == 2
    assert taxonomy.required_documents == ["police_report"]


def test_required_documents_defaults_to_empty_list() -> None:
    taxonomy = TaxonomySchema(document_types=_VALID_DOC_TYPES)
    assert taxonomy.required_documents == []


def test_duplicate_document_type_names_raise_validation_error() -> None:
    with pytest.raises(ValidationError, match="duplicate names"):
        TaxonomySchema(
            document_types=[
                DocumentTypeSchema(
                    name="police_report", label="Police Report", description="First"
                ),
                DocumentTypeSchema(
                    name="police_report", label="Police Report Dupe", description="Second"
                ),
            ],
            required_documents=[],
        )


def test_required_documents_referencing_undeclared_type_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="undeclared types"):
        TaxonomySchema(
            document_types=_VALID_DOC_TYPES,
            required_documents=["nonexistent_type"],
        )


def test_unknown_field_on_document_type_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        DocumentTypeSchema.model_validate(
            {
                "name": "police_report",
                "label": "Police Report",
                "description": "...",
                "ocr_engine": "simple",
            }
        )


def test_unknown_field_on_taxonomy_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        TaxonomySchema.model_validate(
            {
                "document_types": [
                    {"name": "police_report", "label": "Police Report", "description": "..."}
                ],
                "required_documents": [],
                "llm": {"model": "gpt-4", "deployment": "gpt4"},
            }
        )


def test_error_message_names_the_duplicate_type() -> None:
    with pytest.raises(ValidationError, match="police_report"):
        TaxonomySchema(
            document_types=[
                DocumentTypeSchema(name="police_report", label="A", description="..."),
                DocumentTypeSchema(name="police_report", label="B", description="..."),
            ],
            required_documents=[],
        )


def test_error_message_names_the_undeclared_reference() -> None:
    with pytest.raises(ValidationError, match="ghost_doc"):
        TaxonomySchema(
            document_types=_VALID_DOC_TYPES,
            required_documents=["ghost_doc"],
        )


def test_duplicate_required_documents_entries_raise_validation_error() -> None:
    with pytest.raises(ValidationError, match="duplicate entries"):
        TaxonomySchema(
            document_types=_VALID_DOC_TYPES,
            required_documents=["police_report", "police_report"],
        )
