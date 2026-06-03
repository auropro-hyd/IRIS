"""TaxonomySchema — classification taxonomy for a Product bundle.

Lifted from the PoC ClassificationConfig; tightened with uniqueness and
referential-integrity validators.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentTypeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Identifier used in required_documents references")
    label: str = Field(description="Human-readable label shown in the reviewer UI")
    description: str = Field(description="Rich description fed to the LLM classifier prompt")


class TaxonomySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_types: list[DocumentTypeSchema] = Field(
        description="Catalogue of document types the classifier can assign"
    )
    required_documents: list[str] = Field(
        default_factory=list,
        description="Names from document_types that are required for this product",
    )

    @model_validator(mode="after")
    def _document_type_names_are_unique(self) -> "TaxonomySchema":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for dt in self.document_types:
            if dt.name in seen:
                duplicates.add(dt.name)
            seen.add(dt.name)
        if duplicates:
            raise ValueError(f"document_types contains duplicate names: {sorted(duplicates)}")
        return self

    @model_validator(mode="after")
    def _required_documents_reference_declared_types(self) -> "TaxonomySchema":
        declared = {dt.name for dt in self.document_types}
        unknown = [r for r in self.required_documents if r not in declared]
        if unknown:
            raise ValueError(
                f"required_documents references undeclared types: {unknown}. "
                f"Declared: {sorted(declared)}"
            )
        return self
