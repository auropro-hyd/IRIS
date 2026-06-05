"""ProductSchema: root schema for a fully validated Product bundle.

Combines the fields from product.yaml (region, retention, adapters) with the
three sub-schemas loaded from the sibling YAML files by the loader.
"""

from iris_config.schema.adapters import AdaptersSchema
from iris_config.schema.extraction import ExtractionSchema
from iris_config.schema.prompts import PromptSchema
from iris_config.schema.taxonomy import TaxonomySchema
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: str = Field(description="Jurisdiction region code")
    retention_days: int = Field(gt=0, description="Data retention period in days")
    adapters: AdaptersSchema
    taxonomy: TaxonomySchema
    extraction: ExtractionSchema
    prompts: PromptSchema

    @model_validator(mode="after")
    def _taxonomy_must_have_at_least_one_document_type(self) -> "ProductSchema":
        if not self.taxonomy.document_types:
            raise ValueError("taxonomy.document_types must contain at least one entry")
        return self
