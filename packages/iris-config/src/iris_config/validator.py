"""Format Pydantic ValidationErrors into rich ConfigLoadErrors.

T026: each error line includes bundle slug, file path, field path (loc),
the invalid value, and Pydantic's message (which for Literal types lists
the valid options as the suggested fix).
"""

from pathlib import Path

from pydantic_core import ValidationError

from iris_config.exceptions import ConfigLoadError


def format_validation_error(
    error: ValidationError,
    slug: str,
    file: Path,
) -> ConfigLoadError:
    """Convert *error* into a :class:`ConfigLoadError` with full context.

    Args:
        error: The Pydantic ValidationError to format.
        slug:  Bundle identifier (e.g. ``commercial-auto-claims/in``).
        file:  The YAML file whose content triggered the error.

    Returns:
        A :class:`ConfigLoadError` whose ``str()`` contains slug, file path,
        field path, invalid value, and the Pydantic message (valid options).
    """
    lines = [f"Bundle '{slug}' — {file}:"]
    for err in error.errors():
        loc = " -> ".join(str(p) for p in err["loc"]) if err["loc"] else "<model>"
        val = err.get("input")
        msg = err["msg"]
        lines.append(f"  [{loc}] {msg}; got: {val!r}")
    return ConfigLoadError(slug=slug, file=file, message="\n".join(lines))
