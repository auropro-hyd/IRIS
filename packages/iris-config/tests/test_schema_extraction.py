"""Unit tests for iris_config.schema.extraction (T023)."""

import pytest
from iris_config.schema.extraction import ArrayItemSchema, ExtractionSchema, FieldSchema
from pydantic_core import ValidationError

_VALID_FIELD = FieldSchema(
    name="date_of_loss",
    label="Date of Loss",
    type="date",
    required=True,
    description="Date when the incident occurred",
)


# ── happy path ────────────────────────────────────────────────────────────────


def test_valid_extraction_schema_loads() -> None:
    schema = ExtractionSchema(fields=[_VALID_FIELD])
    assert len(schema.fields) == 1


def test_all_field_types_are_accepted() -> None:
    for field_type in ("text", "number", "date", "checkbox", "phone", "email", "textarea"):
        field = FieldSchema(name="f", label="F", type=field_type, description="d")  # type: ignore[arg-type]
        assert field.type == field_type


def test_field_with_allowed_values_loads() -> None:
    field = FieldSchema(
        name="loss_type",
        label="Loss Type",
        type="text",
        description="Type of loss",
        allowed_values=["Collision", "Theft", "Vandalism"],
    )
    assert field.allowed_values == ["Collision", "Theft", "Vandalism"]


def test_field_with_valid_regex_loads() -> None:
    field = FieldSchema(
        name="policy_number",
        label="Policy Number",
        type="text",
        description="Policy number",
        regex=r"^[A-Z]{2}\d{8}$",
    )
    assert field.regex == r"^[A-Z]{2}\d{8}$"


def test_field_with_valid_range_loads() -> None:
    field = FieldSchema(
        name="speed_limit",
        label="Speed Limit",
        type="number",
        description="Posted speed limit",
        range=(0.0, 120.0),
    )
    assert field.range == (0.0, 120.0)


def test_array_field_with_items_loads() -> None:
    field = FieldSchema(
        name="injured_parties",
        label="Injured Parties",
        type="array",
        description="List of injured parties",
        items=[
            ArrayItemSchema(name="name", label="Name"),
            ArrayItemSchema(name="injury", label="Injury"),
        ],
    )
    assert len(field.items) == 2  # type: ignore[arg-type]


# ── regex validator ───────────────────────────────────────────────────────────


def test_invalid_regex_pattern_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="invalid regex"):
        FieldSchema(
            name="policy_number",
            label="Policy Number",
            type="text",
            description="d",
            regex="[unclosed",
        )


def test_invalid_regex_error_includes_the_bad_pattern() -> None:
    with pytest.raises(ValidationError, match=r"\[unclosed"):
        FieldSchema(name="f", label="F", type="text", description="d", regex="[unclosed")


# ── range validator ───────────────────────────────────────────────────────────


def test_range_on_non_number_field_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="type='number'"):
        FieldSchema(name="f", label="F", type="text", description="d", range=(0.0, 100.0))


def test_range_min_equal_to_max_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="less than"):
        FieldSchema(name="f", label="F", type="number", description="d", range=(50.0, 50.0))


def test_range_min_greater_than_max_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="less than"):
        FieldSchema(name="f", label="F", type="number", description="d", range=(100.0, 0.0))


# ── items validator ───────────────────────────────────────────────────────────


def test_items_on_non_array_field_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="type='array'"):
        FieldSchema(
            name="f",
            label="F",
            type="text",
            description="d",
            items=[ArrayItemSchema(name="col", label="Col")],
        )


# ── ExtractionSchema guards ───────────────────────────────────────────────────


def test_empty_fields_list_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ExtractionSchema(fields=[])


def test_unknown_field_on_field_schema_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        FieldSchema.model_validate(
            {"name": "f", "label": "F", "type": "text", "description": "d", "unknown_key": "x"}
        )
