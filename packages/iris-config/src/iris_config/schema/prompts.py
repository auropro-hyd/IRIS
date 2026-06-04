"""PromptSchema: prompt template paths and declared variables for a Product bundle.

Each template declares its path (.j2) and the variable names it expects.
The loader calls validate_against_template() after reading the file to verify
that every Jinja2 variable in the template was declared.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PromptTemplateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(description="Path to the Jinja2 template, relative to the bundle directory")
    variables: list[str] = Field(
        min_length=1,
        description="Variable names the template expects",
    )

    @field_validator("path", mode="after")
    @classmethod
    def _path_must_be_j2(cls, v: str) -> str:
        if not v.endswith(".j2"):
            raise ValueError(f"template path must end with .j2, got: {v!r}")
        return v

    @field_validator("variables", mode="after")
    @classmethod
    def _variables_must_be_non_blank(cls, v: list[str]) -> list[str]:
        blanks = [i for i, name in enumerate(v) if not name.strip()]
        if blanks:
            raise ValueError(f"variables at indices {blanks} are blank")
        return v

    def validate_against_template(self, template_content: str) -> None:
        """Raise ValueError if template uses a variable not listed in self.variables."""
        used = set(re.findall(r"\{\{\s*(\w+)", template_content))
        declared = set(self.variables)
        undeclared = used - declared
        if undeclared:
            raise ValueError(
                f"template uses undeclared variables: {sorted(undeclared)}. "
                f"Declared: {sorted(declared)}"
            )


class PromptSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classify: PromptTemplateSchema
    extract: PromptTemplateSchema
    summarize: PromptTemplateSchema
