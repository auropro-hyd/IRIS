"""Jinja2 template loader scoped to a Product bundle's prompts directory.

All templates are validated at construction time: any template that references
a variable not listed in the bundle's declared variables raises immediately,
before any document is processed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import jinja2

from iris_agents.errors import AgentError


class _TemplateSpec(Protocol):
    """Shape of a single prompt template entry from the bundle config."""

    path: str

    def validate_against_template(self, content: str) -> None: ...


class _PromptsSchema(Protocol):
    """Shape of the prompts block from the bundle config."""

    classify: _TemplateSpec
    extract: _TemplateSpec
    summarize: _TemplateSpec


class TemplateLoader:
    """Loads and validates all prompt templates for a Product bundle.

    Raises ValueError at construction if any template uses a variable not
    declared in the bundle's prompts config. This surfaces misconfigured
    Product bundles at startup rather than mid-classification.
    """

    def __init__(self, bundle_dir: Path, prompts: _PromptsSchema) -> None:
        env = jinja2.Environment(
            undefined=jinja2.StrictUndefined,
            autoescape=False,
        )
        specs: list[tuple[str, _TemplateSpec]] = [
            ("classify", prompts.classify),
            ("extract", prompts.extract),
            ("summarize", prompts.summarize),
        ]
        self._templates: dict[str, jinja2.Template] = {}
        for name, spec in specs:
            p = Path(spec.path)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError(
                    f"template path {spec.path!r} must be relative and within the bundle"
                )
            try:
                content = (bundle_dir / spec.path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ValueError(
                    f"failed to read template {name!r} at {spec.path!r}: {exc}"
                ) from exc
            spec.validate_against_template(content)
            self._templates[name] = env.from_string(content)

    def render(self, name: str, **variables: object) -> str:
        """Render a named template with the supplied variables.

        Raises:
            AgentError: name is not one of the registered template names.
            jinja2.UndefinedError: a declared variable was not supplied.
        """
        try:
            template = self._templates[name]
        except KeyError:
            raise AgentError(f"no template registered under {name!r}") from None
        return template.render(**variables)
