"""Exceptions raised by the iris_config loader and validator."""

from pathlib import Path


class ConfigLoadError(Exception):
    """A Product bundle could not be loaded.

    Covers file-level failures: missing files, YAML parse errors, and
    unreadable files. Also serves as the base for schema-level failures.

    Attributes:
        slug: Bundle identifier, e.g. ``commercial-auto-claims/in``.
        file: Path to the file inside the bundle that caused the error.
    """

    def __init__(self, slug: str, file: Path, message: str) -> None:
        self.slug = slug
        self.file = file
        super().__init__(message)


class ConfigValidationError(ConfigLoadError):
    """A Product bundle failed schema validation.

    Raised when the YAML files are readable but their content does not
    satisfy the Pydantic schema. Callers that need to distinguish a
    missing-file error from a bad-value error can catch this specifically.

    Inherits ``slug`` and ``file`` from :class:`ConfigLoadError`.
    """
