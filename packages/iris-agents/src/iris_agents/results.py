"""Result types returned by DocumentClassifier and FieldExtractor.

Classification mirrors the per-document fields from the PoC's ClassifiedDocument,
with IRIS additions (reason, citations, missing_documents). The case-level envelope
(config metadata, list of all classified docs, summary) is assembled by the caller,
not by classify() itself.

Extraction mirrors the PoC's ExtractionResult, extended with validation_errors.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Citation(BaseModel):
    """A page region used to support a classification or extraction decision."""

    model_config = ConfigDict(extra="forbid")

    page: int
    bounding_box: list[float] = Field(default_factory=list)
    text: str | None = None

    @field_validator("bounding_box")
    @classmethod
    def _bounding_box_shape(cls, v: list[float]) -> list[float]:
        if v and len(v) != 4:
            raise ValueError("bounding_box must be empty or exactly [x, y, width, height]")
        return v


class MissingDocument(BaseModel):
    """A required document not satisfied by the current classification."""

    model_config = ConfigDict(extra="forbid")

    document_type: str
    label: str
    coverage: str | None = None
    reason: str | None = None


class MissingDocuments(BaseModel):
    """Missing documents split by requirement category."""

    model_config = ConfigDict(extra="forbid")

    product_mandatory: list[MissingDocument] = Field(default_factory=list)
    coverage_mandatory: list[MissingDocument] = Field(default_factory=list)


class Classification(BaseModel):
    """Per-document result from DocumentClassifier.

    document_type is the matched taxonomy id (e.g. "fnol_form"), or the literal
    string "unknown" when no taxonomy entry matches (US2). citations carry the
    page(s) and bounding boxes the classifier used (US1). reason is required
    non-empty when document_type is "unknown" so the reviewer always sees an
    explanation. missing_documents lists required docs this single document does
    not satisfy within the submission context.
    """

    model_config = ConfigDict(extra="forbid")

    document_type: str = "unknown"
    label: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    missing_documents: MissingDocuments = Field(default_factory=MissingDocuments)

    @model_validator(mode="after")
    def _reason_required_for_unknown(self) -> Classification:
        if self.document_type == "unknown" and not self.reason:
            raise ValueError("reason must be non-empty when document_type is 'unknown' (US2)")
        return self


class FieldValidationError(BaseModel):
    """A field that was extracted but failed a declared validator.

    This is a data container stored in Extraction.validation_errors, not a
    throwable exception. The rest of the Extraction is still returned; errors
    do not abort the extraction.
    """

    model_config = ConfigDict(extra="forbid")

    field: str
    value: Any
    rule: str
    message: str


class ExtractedField(BaseModel):
    """A single extracted field with its value, confidence, and citation."""

    model_config = ConfigDict(extra="forbid")

    value: Any = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    cited: str | None = None


class Extraction(BaseModel):
    """Full response from FieldExtractor.

    Mirrors the PoC's ExtractionResult: carries config metadata and per-field
    results. validation_errors lists fields that failed declared validators;
    those fields still appear in fields with their raw extracted value.
    """

    model_config = ConfigDict(extra="forbid")

    config_name: str
    config_version: str
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    validation_errors: list[FieldValidationError] = Field(default_factory=list)
