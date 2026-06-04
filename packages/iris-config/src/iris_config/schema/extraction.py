"""ExtractionSchema: FNOL field extraction schema for a Product bundle.

Lifted from the PoC ExtractionConfig; adds regex and range validator slots
with compile-time validation. LLMConfig, name/version, and runtime models
(ExtractedField, FormFieldResponse, etc.) are stripped -- those belong in
adapters.yaml and workstream 005 respectively.
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FieldType = Literal["text", "number", "date", "checkbox", "phone", "email", "textarea", "array"]
ArrayItemType = Literal["text", "number", "date", "currency"]


class FieldGroupSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str


class ArrayItemSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    type: ArrayItemType = "text"


class FieldSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    type: FieldType
    required: bool = False
    description: str
    allowed_values: list[str] | None = None
    examples: list[Any] | None = None
    group: FieldGroupSchema | None = None
    items: list[ArrayItemSchema] | None = None
    regex: str | None = None
    range: tuple[float, float] | None = None

    @field_validator("regex", mode="after")
    @classmethod
    def _regex_must_compile(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"invalid regex pattern '{v}': {exc}") from exc
        return v

    @model_validator(mode="after")
    def _range_only_on_number_fields(self) -> "FieldSchema":
        if self.range is not None and self.type != "number":
            raise ValueError(f"range is only valid for type='number', got type='{self.type}'")
        return self

    @model_validator(mode="after")
    def _range_min_less_than_max(self) -> "FieldSchema":
        if self.range is not None and self.range[0] >= self.range[1]:
            raise ValueError(
                f"range[0] ({self.range[0]}) must be less than range[1] ({self.range[1]})"
            )
        return self

    @model_validator(mode="after")
    def _items_only_on_array_fields(self) -> "FieldSchema":
        if self.items is not None and self.type != "array":
            raise ValueError(f"items is only valid for type='array', got type='{self.type}'")
        return self


class ExtractionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[FieldSchema] = Field(
        min_length=1,
        description="Ordered list of FNOL fields to extract",
    )
