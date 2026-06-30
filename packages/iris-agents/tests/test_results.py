"""T051 acceptance: round-trip model_validate for all result types."""

from __future__ import annotations

import pytest
from iris_agents.results import (
    Citation,
    Classification,
    ExtractedField,
    Extraction,
    FieldValidationError,
    MissingDocument,
    MissingDocuments,
)
from pydantic import ValidationError

# ── Citation ──────────────────────────────────────────────────────────────────


def test_citation_round_trip() -> None:
    data = {"page": 1, "bounding_box": [10.0, 20.0, 100.0, 50.0], "text": "FNOL Form"}
    obj = Citation.model_validate(data)
    assert obj.page == 1
    assert obj.bounding_box == [10.0, 20.0, 100.0, 50.0]
    assert obj.text == "FNOL Form"
    assert Citation.model_validate(obj.model_dump()) == obj


def test_citation_optional_fields_default() -> None:
    obj = Citation.model_validate({"page": 2})
    assert obj.bounding_box == []
    assert obj.text is None


# ── MissingDocument ───────────────────────────────────────────────────────────


def test_missing_document_round_trip() -> None:
    data = {
        "document_type": "police_report",
        "label": "Police Report",
        "coverage": "comprehensive",
        "reason": "Required for comprehensive coverage claims",
    }
    obj = MissingDocument.model_validate(data)
    assert obj.document_type == "police_report"
    assert obj.coverage == "comprehensive"
    assert MissingDocument.model_validate(obj.model_dump()) == obj


def test_missing_document_optional_fields_default_none() -> None:
    obj = MissingDocument.model_validate({"document_type": "fnol_form", "label": "FNOL"})
    assert obj.coverage is None
    assert obj.reason is None


# ── MissingDocuments ──────────────────────────────────────────────────────────


def test_missing_documents_round_trip() -> None:
    data = {
        "product_mandatory": [
            {
                "document_type": "fnol_form",
                "label": "FNOL Form",
                "coverage": None,
                "reason": "Required for all claims",
            },
        ],
        "coverage_mandatory": [
            {
                "document_type": "police_report",
                "label": "Police Report",
                "coverage": "comprehensive",
                "reason": "Required for comprehensive coverage",
            },
        ],
    }
    obj = MissingDocuments.model_validate(data)
    assert len(obj.product_mandatory) == 1
    assert len(obj.coverage_mandatory) == 1
    assert obj.product_mandatory[0].document_type == "fnol_form"
    assert obj.coverage_mandatory[0].coverage == "comprehensive"
    assert MissingDocuments.model_validate(obj.model_dump()) == obj


def test_missing_documents_defaults_empty() -> None:
    obj = MissingDocuments.model_validate({})
    assert obj.product_mandatory == []
    assert obj.coverage_mandatory == []


# ── Classification ────────────────────────────────────────────────────────────


def test_classification_round_trip() -> None:
    data = {
        "document_type": "fnol_form",
        "label": "FNOL Form",
        "confidence": 0.95,
        "reason": "Document contains FNOL header and policy number fields.",
        "citations": [
            {"page": 1, "bounding_box": [0.0, 0.0, 200.0, 50.0], "text": "FNOL Header"},
        ],
        "missing_documents": {
            "product_mandatory": [],
            "coverage_mandatory": [],
        },
    }
    obj = Classification.model_validate(data)
    assert obj.document_type == "fnol_form"
    assert obj.confidence == pytest.approx(0.95)
    assert len(obj.citations) == 1
    assert obj.citations[0].page == 1
    assert Classification.model_validate(obj.model_dump()) == obj


def test_classification_unknown_path() -> None:
    obj = Classification.model_validate(
        {"document_type": "unknown", "confidence": 0.0, "reason": "No taxonomy match found."}
    )
    assert obj.document_type == "unknown"
    assert obj.label is None
    assert obj.reason == "No taxonomy match found."


def test_classification_unknown_default_document_type() -> None:
    obj = Classification.model_validate({"confidence": 0.0, "reason": "No match."})
    assert obj.document_type == "unknown"


def test_classification_unknown_without_reason_raises() -> None:
    with pytest.raises(ValidationError, match="reason"):
        Classification.model_validate({"document_type": "unknown", "confidence": 0.0})


def test_classification_unknown_empty_reason_raises() -> None:
    with pytest.raises(ValidationError, match="reason"):
        Classification.model_validate({"document_type": "unknown", "confidence": 0.0, "reason": ""})


def test_classification_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        Classification.model_validate({"confidence": 1.5})
    with pytest.raises(ValidationError):
        Classification.model_validate({"confidence": -0.1})


def test_classification_known_type_defaults() -> None:
    obj = Classification.model_validate({"document_type": "fnol_form", "confidence": 0.8})
    assert obj.document_type == "fnol_form"
    assert obj.label is None
    assert obj.reason is None
    assert obj.citations == []
    assert obj.missing_documents.product_mandatory == []
    assert obj.missing_documents.coverage_mandatory == []


def test_classification_with_missing_documents() -> None:
    data = {
        "document_type": "fnol_form",
        "confidence": 0.92,
        "missing_documents": {
            "product_mandatory": [
                {
                    "document_type": "police_report",
                    "label": "Police Report",
                    "reason": "Required for all claims",
                },
            ],
            "coverage_mandatory": [
                {
                    "document_type": "medical_report",
                    "label": "Medical Report",
                    "coverage": "medical",
                    "reason": "Required for medical coverage",
                },
            ],
        },
    }
    obj = Classification.model_validate(data)
    assert len(obj.missing_documents.product_mandatory) == 1
    assert len(obj.missing_documents.coverage_mandatory) == 1
    assert obj.missing_documents.coverage_mandatory[0].coverage == "medical"


def test_classification_with_multiple_citations() -> None:
    data = {
        "document_type": "police_report",
        "confidence": 0.88,
        "citations": [
            {"page": 1, "bounding_box": [0.0, 0.0, 100.0, 30.0], "text": "Incident Report"},
            {"page": 2, "bounding_box": [50.0, 10.0, 200.0, 40.0], "text": "Officer Signature"},
        ],
    }
    obj = Classification.model_validate(data)
    assert len(obj.citations) == 2
    assert obj.citations[1].page == 2


# ── FieldValidationError ──────────────────────────────────────────────────────


def test_field_validation_error_round_trip() -> None:
    data = {
        "field": "incident_date",
        "value": "01-02-2026",
        "rule": "iso_8601",
        "message": "Expected YYYY-MM-DD, got 01-02-2026",
    }
    obj = FieldValidationError.model_validate(data)
    assert obj.field == "incident_date"
    assert obj.rule == "iso_8601"
    assert FieldValidationError.model_validate(obj.model_dump()) == obj


def test_field_validation_error_value_can_be_any_type() -> None:
    for val in [None, 42, 3.14, True, ["a", "b"], {"nested": 1}]:
        obj = FieldValidationError.model_validate(
            {"field": "f", "value": val, "rule": "enum", "message": "bad"}
        )
        assert obj.value == val


# ── ExtractedField ────────────────────────────────────────────────────────────


def test_extracted_field_round_trip() -> None:
    data = {"value": "AH-99200-FT-2026", "confidence": 0.99, "cited": "Header section"}
    obj = ExtractedField.model_validate(data)
    assert obj.value == "AH-99200-FT-2026"
    assert obj.cited == "Header section"
    assert ExtractedField.model_validate(obj.model_dump()) == obj


def test_extracted_field_null_value_and_citation() -> None:
    obj = ExtractedField.model_validate({"value": None, "confidence": 0.0, "cited": None})
    assert obj.value is None
    assert obj.cited is None


# ── Extraction ────────────────────────────────────────────────────────────────


def test_extraction_round_trip() -> None:
    data = {
        "config_name": "commercial-auto-fnol",
        "config_version": "1.0",
        "fields": {
            "policy_number": {"value": "AH-99200-FT-2026", "confidence": 0.99, "cited": "Header"},
            "date_of_loss": {"value": "2026-02-01", "confidence": 0.98, "cited": "Loss Details"},
            "claimant_name": {
                "value": "Swift Delivery Solutions, LLC",
                "confidence": 0.97,
                "cited": "Insured section",
            },
        },
        "validation_errors": [],
    }
    obj = Extraction.model_validate(data)
    assert obj.config_name == "commercial-auto-fnol"
    assert obj.config_version == "1.0"
    assert obj.fields["policy_number"].value == "AH-99200-FT-2026"
    assert obj.validation_errors == []
    assert Extraction.model_validate(obj.model_dump()) == obj


def test_extraction_with_validation_errors() -> None:
    data = {
        "config_name": "commercial-auto-fnol",
        "config_version": "1.0",
        "fields": {
            "incident_date": {"value": "01-02-2026", "confidence": 0.85, "cited": "Section 2"},
            "claim_type": {"value": "INVALID", "confidence": 0.6, "cited": "Section 1"},
        },
        "validation_errors": [
            {
                "field": "incident_date",
                "value": "01-02-2026",
                "rule": "iso_8601",
                "message": "Expected YYYY-MM-DD",
            },
            {
                "field": "claim_type",
                "value": "INVALID",
                "rule": "enum",
                "message": "Not in allowed values",
            },
        ],
    }
    obj = Extraction.model_validate(data)
    assert len(obj.validation_errors) == 2
    assert obj.validation_errors[0].rule == "iso_8601"
    assert obj.validation_errors[1].rule == "enum"
    assert Extraction.model_validate(obj.model_dump()) == obj


def test_extraction_empty_fields_and_errors() -> None:
    obj = Extraction.model_validate({"config_name": "test-config", "config_version": "1.0"})
    assert obj.fields == {}
    assert obj.validation_errors == []
