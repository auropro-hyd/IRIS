"""Result types returned by DocumentClassifier and FieldExtractor.

Classification mirrors the per-document fields from the PoC's ClassifiedDocument,
with IRIS additions (reason, citations, missing_documents). The case-level envelope
(config metadata, list of all classified docs, summary) is assembled by the caller,
not by classify() itself.

Extraction mirrors the PoC's ExtractionResult, extended with validation_errors.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A page region used to support a classification or extraction decision."""

    page: int
    bounding_box: list[float] = Field(default_factory=list)  # [x, y, width, height]
    text: str | None = None


class MissingDocument(BaseModel):
    """A required document not satisfied by the current classification."""

    document_type: str
    label: str
    coverage: str | None = None
    reason: str | None = None


class MissingDocuments(BaseModel):
    """Missing documents split by requirement category."""

    product_mandatory: list[MissingDocument] = Field(default_factory=list)
    coverage_mandatory: list[MissingDocument] = Field(default_factory=list)


class Classification(BaseModel):
    """Per-document result from DocumentClassifier.

    document_type is None when no taxonomy entry matches (the unknown path).
    reason is required non-empty for the unknown outcome (US2). citations
    carry the page(s) and bounding boxes the classifier used (US1).
    missing_documents lists required docs that this single document does not
    itself satisfy within the submission context.
    """

    document_type: str | None = None
    label: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    missing_documents: MissingDocuments = Field(default_factory=MissingDocuments)


class FieldValidationError(BaseModel):
    """A field that was extracted but failed a declared validator.

    The rest of the Extraction is still returned; errors do not abort
    the extraction.
    """

    field: str
    value: Any
    rule: str
    message: str


class ExtractedField(BaseModel):
    """A single extracted field with its value, confidence, and citation."""

    value: Any = None
    confidence: float = Field(ge=0.0, le=1.0)
    cited: str | None = None


class Extraction(BaseModel):
    """Full response from FieldExtractor.

    Mirrors the PoC's ExtractionResult: carries config metadata and per-field
    results. validation_errors lists fields that failed declared validators;
    those fields still appear in fields with their raw extracted value.
    """

    config_name: str
    config_version: str
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    validation_errors: list[FieldValidationError] = Field(default_factory=list)
