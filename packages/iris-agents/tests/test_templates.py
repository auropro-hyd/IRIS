"""T052 acceptance: TemplateLoader validates templates at load time, not render time."""

from __future__ import annotations

from pathlib import Path

import jinja2
import pytest
from iris_agents.errors import AgentError
from iris_agents.templates import TemplateLoader
from iris_config.schema.prompts import PromptSchema

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_bundle(tmp_path: Path, templates: dict[str, tuple[str, list[str]]]) -> PromptSchema:
    """Write template files into tmp_path and return a PromptSchema.

    templates: {name: (template_content, declared_variables)}
    """
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    raw: dict[str, dict[str, object]] = {}
    for name, (content, variables) in templates.items():
        path = f"prompts/{name}.j2"
        (tmp_path / path).write_text(content)
        raw[name] = {"path": path, "variables": variables}
    return PromptSchema.model_validate(raw)


def _minimal_bundle(tmp_path: Path, *, classify: str, classify_vars: list[str]) -> PromptSchema:
    """Helper for tests that only care about the classify template."""
    return _make_bundle(
        tmp_path,
        {
            "classify": (classify, classify_vars),
            "extract": ("Extract {{ fields }} from {{ ocr_text }}", ["fields", "ocr_text"]),
            "summarize": ("Summarise {{ claim_data }}", ["claim_data"]),
        },
    )


# ── load-time validation ──────────────────────────────────────────────────────


def test_valid_template_loads_without_error(tmp_path: Path) -> None:
    prompts = _minimal_bundle(
        tmp_path,
        classify="Classify this document: {{ ocr_text }} using {{ taxonomy }}",
        classify_vars=["ocr_text", "taxonomy"],
    )
    loader = TemplateLoader(tmp_path, prompts)
    assert loader is not None


def test_undeclared_variable_raises_at_load_time(tmp_path: Path) -> None:
    prompts = _minimal_bundle(
        tmp_path,
        classify="Classify {{ ocr_text }} and {{ secret_var }}",
        classify_vars=["ocr_text"],  # secret_var not declared
    )
    with pytest.raises(ValueError, match="undeclared"):
        TemplateLoader(tmp_path, prompts)


def test_error_message_names_the_undeclared_variable(tmp_path: Path) -> None:
    prompts = _minimal_bundle(
        tmp_path,
        classify="{{ ocr_text }} and {{ missing_one }}",
        classify_vars=["ocr_text"],
    )
    with pytest.raises(ValueError, match="missing_one"):
        TemplateLoader(tmp_path, prompts)


def test_fully_declared_template_with_multiple_variables(tmp_path: Path) -> None:
    prompts = _minimal_bundle(
        tmp_path,
        classify="Classify {{ ocr_text }} using {{ taxonomy }} for {{ product }}",
        classify_vars=["ocr_text", "taxonomy", "product"],
    )
    loader = TemplateLoader(tmp_path, prompts)
    result = loader.render("classify", ocr_text="text", taxonomy="types", product="auto")
    assert "text" in result
    assert "types" in result


# ── render behaviour ──────────────────────────────────────────────────────────


def test_render_produces_expected_output(tmp_path: Path) -> None:
    prompts = _minimal_bundle(
        tmp_path,
        classify="Document type: {{ ocr_text }}",
        classify_vars=["ocr_text"],
    )
    loader = TemplateLoader(tmp_path, prompts)
    result = loader.render("classify", ocr_text="FNOL Form")
    assert result == "Document type: FNOL Form"


def test_render_missing_variable_raises_at_render_time(tmp_path: Path) -> None:
    prompts = _minimal_bundle(
        tmp_path,
        classify="Type: {{ ocr_text }}",
        classify_vars=["ocr_text"],
    )
    loader = TemplateLoader(tmp_path, prompts)
    with pytest.raises(jinja2.UndefinedError):
        loader.render("classify")  # ocr_text not supplied


def test_render_unknown_template_name_raises(tmp_path: Path) -> None:
    prompts = _minimal_bundle(
        tmp_path,
        classify="Type: {{ ocr_text }}",
        classify_vars=["ocr_text"],
    )
    loader = TemplateLoader(tmp_path, prompts)
    with pytest.raises(AgentError):
        loader.render("nonexistent")


def test_all_three_templates_are_accessible(tmp_path: Path) -> None:
    prompts = _make_bundle(
        tmp_path,
        {
            "classify": ("Classify {{ ocr_text }}", ["ocr_text"]),
            "extract": ("Extract {{ fields }} from {{ ocr_text }}", ["fields", "ocr_text"]),
            "summarize": ("Summarise {{ claim_data }}", ["claim_data"]),
        },
    )
    loader = TemplateLoader(tmp_path, prompts)
    assert "Classify" in loader.render("classify", ocr_text="x")
    assert "Extract" in loader.render("extract", fields="f", ocr_text="x")
    assert "Summarise" in loader.render("summarize", claim_data="d")


# ── smoke test against real bundle ────────────────────────────────────────────


def test_real_commercial_auto_bundle_loads() -> None:
    bundle_dir = Path("config/products/commercial-auto-claims/in")
    if not bundle_dir.exists():
        pytest.skip("real bundle not present")
    import yaml

    with open(bundle_dir / "product.yaml") as f:
        raw = yaml.safe_load(f)
    prompts = PromptSchema.model_validate(raw["prompts"])
    loader = TemplateLoader(bundle_dir, prompts)
    result = loader.render("classify", taxonomy="fnol_form", ocr_text="sample")
    assert len(result) > 0
