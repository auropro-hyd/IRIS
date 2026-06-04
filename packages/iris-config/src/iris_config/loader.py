"""Walk a config/products/ tree and return a ProductRegistry.

Bundle layout expected under *root*:
    <root>/<line-of-business>/<jurisdiction>/
        product.yaml     # region, retention_days, adapters, prompts
        taxonomy.yaml    # document_types, required_documents
        extraction.yaml  # fields list
        prompts/         # *.j2 template files declared in product.yaml
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic_core import ValidationError

from iris_config.exceptions import ConfigLoadError
from iris_config.schema.product import ProductSchema
from iris_config.validator import format_validation_error


@dataclass
class ProductConfig:
    """A validated Product bundle with its filesystem context."""

    slug: str
    bundle_dir: Path
    schema: ProductSchema


ProductRegistry = dict[str, ProductConfig]


def _read_yaml(path: Path, slug: str) -> dict[str, Any]:
    """Read and parse *path* as a YAML mapping.

    Raises:
        ConfigLoadError: if the file is missing, unreadable, or not a mapping.
    """
    if not path.exists():
        raise ConfigLoadError(
            slug=slug,
            file=path,
            message=f"Bundle '{slug}' — {path}: required file not found",
        )
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigLoadError(
            slug=slug,
            file=path,
            message=f"Bundle '{slug}' — {path}: YAML parse error: {exc}",
        ) from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigLoadError(
            slug=slug,
            file=path,
            message=f"Bundle '{slug}' — {path}: cannot read file: {exc}",
        ) from exc
    if not isinstance(data, dict):
        raise ConfigLoadError(
            slug=slug,
            file=path,
            message=(
                f"Bundle '{slug}' — {path}: expected a YAML mapping, " f"got {type(data).__name__}"
            ),
        )
    return data  # type: ignore[return-value]


def _locate_error_file(
    loc: tuple[str | int, ...],
    product_file: Path,
    taxonomy_file: Path,
    extraction_file: Path,
) -> Path:
    """Map a Pydantic error location tuple to its source YAML file."""
    if not loc:
        return product_file
    first = str(loc[0])
    if first == "taxonomy":
        return taxonomy_file
    if first == "extraction":
        return extraction_file
    return product_file


def load_bundle(bundle_dir: Path, slug: str) -> ProductConfig:
    """Load and validate a single Product bundle from *bundle_dir*.

    Args:
        bundle_dir: Path to the directory containing product.yaml.
        slug:       Identifier string for this bundle (used in errors).

    Returns:
        A :class:`ProductConfig` holding the validated schema and context.

    Raises:
        ConfigLoadError: If any required file is missing, malformed, or fails
                         schema validation.
    """
    product_file = bundle_dir / "product.yaml"
    taxonomy_file = bundle_dir / "taxonomy.yaml"
    extraction_file = bundle_dir / "extraction.yaml"

    product_data = _read_yaml(product_file, slug)
    taxonomy_data = _read_yaml(taxonomy_file, slug)
    extraction_data = _read_yaml(extraction_file, slug)

    merged: dict[str, Any] = {
        **product_data,
        "taxonomy": taxonomy_data,
        "extraction": extraction_data,
    }

    try:
        schema = ProductSchema.model_validate(merged)
    except ValidationError as exc:
        first_loc = exc.errors()[0]["loc"]
        file = _locate_error_file(first_loc, product_file, taxonomy_file, extraction_file)
        raise format_validation_error(exc, slug, file) from exc

    for slot in ("classify", "extract", "summarize"):
        tmpl = getattr(schema.prompts, slot)
        j2_path = bundle_dir / tmpl.path
        if not j2_path.exists():
            raise ConfigLoadError(
                slug=slug,
                file=j2_path,
                message=f"Bundle '{slug}' — {j2_path}: template file not found",
            )
        try:
            content = j2_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ConfigLoadError(
                slug=slug,
                file=j2_path,
                message=f"Bundle '{slug}' — {j2_path}: cannot read template: {exc}",
            ) from exc
        try:
            tmpl.validate_against_template(content)
        except ValueError as exc:
            raise ConfigLoadError(
                slug=slug,
                file=j2_path,
                message=f"Bundle '{slug}' — {j2_path}: {exc}",
            ) from exc

    return ProductConfig(slug=slug, bundle_dir=bundle_dir, schema=schema)


def load_products(root: Path) -> ProductRegistry:
    """Walk *root* and load every Product bundle found.

    A bundle is any directory that contains a ``product.yaml`` file at any
    depth under *root*.  The slug is the bundle directory's path relative to
    *root* (e.g. ``commercial-auto-claims/in``).

    Args:
        root: Root of the products tree (typically ``config/products/``).

    Returns:
        Mapping of slug → :class:`ProductConfig` for every bundle found.

    Raises:
        ConfigLoadError: On the first malformed or invalid bundle encountered.
    """
    registry: ProductRegistry = {}
    for product_yaml in sorted(root.rglob("product.yaml")):
        bundle_dir = product_yaml.parent
        slug = str(bundle_dir.relative_to(root))
        registry[slug] = load_bundle(bundle_dir, slug)
    return registry
