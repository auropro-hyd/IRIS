"""Format Pydantic ValidationErrors into rich ConfigLoadErrors.

T026: the formatted message has a single header containing the bundle slug
and file path, followed by one line per error with the field path (loc),
Pydantic's message, and the invalid value.
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
