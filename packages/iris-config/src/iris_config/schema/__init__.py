"""iris_config.schema — Pydantic models for Product bundle files."""

from iris_config.schema.adapters import AdaptersSchema
from iris_config.schema.extraction import (
    ArrayItemSchema,
    ExtractionSchema,
    FieldGroupSchema,
    FieldSchema,
)
from iris_config.schema.product import ProductSchema
from iris_config.schema.prompts import PromptSchema, PromptTemplateSchema
from iris_config.schema.taxonomy import DocumentTypeSchema, TaxonomySchema

__all__ = [
    "AdaptersSchema",
    "ArrayItemSchema",
    "DocumentTypeSchema",
    "ExtractionSchema",
    "FieldGroupSchema",
    "FieldSchema",
    "ProductSchema",
    "PromptSchema",
    "PromptTemplateSchema",
    "TaxonomySchema",
]
