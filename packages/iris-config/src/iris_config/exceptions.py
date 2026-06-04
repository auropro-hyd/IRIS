"""Exceptions raised by the iris_config loader and validator."""

from pathlib import Path


class ConfigLoadError(Exception):
    """A Product bundle could not be loaded or validated.

    Attributes:
        slug: Bundle identifier, e.g. ``commercial-auto-claims/in``.
        file: Path to the file inside the bundle that caused the error.
    """

    def __init__(self, slug: str, file: Path, message: str) -> None:
        self.slug = slug
        self.file = file
        super().__init__(message)
