"""Environment variable helpers shared by all LLM adapters."""

from __future__ import annotations

import os


def require_env(name: str) -> str:
    """Return the value of *name* or raise RuntimeError if it is unset or empty."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name!r} is not set")
    return value
