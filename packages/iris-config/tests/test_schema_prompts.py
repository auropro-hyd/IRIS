"""Unit tests for iris_config.schema.prompts (T024)."""

import pytest
from iris_config.schema.prompts import PromptSchema, PromptTemplateSchema
from pydantic_core import ValidationError

_VALID_TEMPLATE = PromptTemplateSchema(
    path="prompts/classify.j2",
    variables=["taxonomy", "ocr_text"],
)

_VALID_PROMPTS = PromptSchema(
    classify=PromptTemplateSchema(path="prompts/classify.j2", variables=["taxonomy", "ocr_text"]),
    extract=PromptTemplateSchema(path="prompts/extract.j2", variables=["fields", "ocr_text"]),
    summarize=PromptTemplateSchema(path="prompts/summarize.j2", variables=["claim_data"]),
)


# ── happy path ────────────────────────────────────────────────────────────────


def test_valid_prompt_schema_loads() -> None:
    assert _VALID_PROMPTS.classify.path == "prompts/classify.j2"
    assert _VALID_PROMPTS.extract.variables == ["fields", "ocr_text"]
    assert _VALID_PROMPTS.summarize.variables == ["claim_data"]


def test_validate_against_template_passes_when_all_variables_declared() -> None:
    _VALID_TEMPLATE.validate_against_template("Classify this: {{ taxonomy }}\nText: {{ ocr_text }}")


# ── T024 acceptance: undeclared variable raises ───────────────────────────────


def test_validate_against_template_raises_for_undeclared_variable() -> None:
    with pytest.raises(ValueError, match="undeclared variables"):
        _VALID_TEMPLATE.validate_against_template("{{ taxonomy }} {{ ocr_text }} {{ unknown_var }}")


def test_error_message_names_the_undeclared_variable() -> None:
    with pytest.raises(ValueError, match="unknown_var"):
        _VALID_TEMPLATE.validate_against_template("{{ taxonomy }} {{ unknown_var }}")


def test_template_with_only_declared_variables_passes() -> None:
    template = PromptTemplateSchema(path="prompts/extract.j2", variables=["fields", "ocr_text"])
    template.validate_against_template("Fields: {{ fields }}\nDoc: {{ ocr_text }}")


def test_dot_access_expression_detects_root_variable() -> None:
    template = PromptTemplateSchema(path="prompts/classify.j2", variables=["taxonomy", "ocr_text"])
    template.validate_against_template("Types: {{ taxonomy.document_types }}\n{{ ocr_text }}")


def test_dot_access_with_undeclared_root_raises() -> None:
    template = PromptTemplateSchema(path="prompts/classify.j2", variables=["taxonomy", "ocr_text"])
    with pytest.raises(ValueError, match="undeclared variables"):
        template.validate_against_template("{{ missing_obj.some_field }}\n{{ ocr_text }}")


def test_filter_expression_detects_variable() -> None:
    template = PromptTemplateSchema(path="prompts/classify.j2", variables=["taxonomy", "ocr_text"])
    template.validate_against_template("{{ taxonomy }}\n{{ ocr_text | trim }}")


def test_filter_expression_with_undeclared_variable_raises() -> None:
    template = PromptTemplateSchema(path="prompts/classify.j2", variables=["taxonomy", "ocr_text"])
    with pytest.raises(ValueError, match="undeclared variables"):
        template.validate_against_template("{{ taxonomy }}\n{{ missing_var | upper }}")


# ── path validator ────────────────────────────────────────────────────────────


def test_path_not_ending_in_j2_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match=".j2"):
        PromptTemplateSchema(path="prompts/classify.txt", variables=["taxonomy"])


def test_absolute_path_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="absolute"):
        PromptTemplateSchema(path="/etc/passwd.j2", variables=["taxonomy"])


def test_path_traversal_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="escape"):
        PromptTemplateSchema(path="../outside/template.j2", variables=["taxonomy"])


# ── variables validator ───────────────────────────────────────────────────────


def test_empty_variables_list_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        PromptTemplateSchema(path="prompts/classify.j2", variables=[])


def test_blank_variable_name_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="blank"):
        PromptTemplateSchema(path="prompts/classify.j2", variables=["taxonomy", ""])


# ── extra field guard ─────────────────────────────────────────────────────────


def test_unknown_field_on_prompt_template_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        PromptTemplateSchema.model_validate(
            {"path": "prompts/classify.j2", "variables": ["taxonomy"], "engine": "jinja2"}
        )
