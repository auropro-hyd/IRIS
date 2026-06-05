"""iris config: Product bundle configuration commands."""

import json
import sys
from pathlib import Path

import click
from iris_config import ConfigLoadError, load_bundle, load_products
from iris_config.schema.extraction import ExtractionSchema
from iris_config.schema.product import ProductSchema
from iris_config.schema.taxonomy import TaxonomySchema

_SCHEMA_MODELS = {
    "product": ProductSchema,
    "taxonomy": TaxonomySchema,
    "extraction": ExtractionSchema,
}


@click.group()
def config() -> None:
    """Validate and inspect Product bundle configuration."""


@config.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path))
def validate(path: Path) -> None:
    """Validate a Product bundle or all bundles under PATH.

    PATH may be a single bundle directory (one that contains product.yaml
    directly) or a root directory containing multiple <lob>/<jurisdiction>/
    bundle subdirectories.

    Exits 0 when every bundle is valid, 1 on the first validation failure.
    """
    try:
        if (path / "product.yaml").exists():
            slug = "/".join(path.parts[-2:])
            load_bundle(path, slug)
            click.echo(f"OK  {slug}")
        else:
            registry = load_products(path)
            for slug in registry:
                click.echo(f"OK  {slug}")
    except ConfigLoadError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


@config.command()
@click.argument("model", type=click.Choice(["product", "taxonomy", "extraction"]))
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="Write JSON Schema to FILE instead of stdout.",
)
def schema(model: str, output: Path | None) -> None:
    """Output the JSON Schema for a Product bundle model.

    MODEL is one of: product, taxonomy, extraction.

    \b
    - product:    merged bundle schema (all four files combined)
    - taxonomy:   schema for taxonomy.yaml (document_types, required_documents)
    - extraction: schema for extraction.yaml (fields list with validators)

    Attach the schema to YAML files in IDEs for editor-time validation.

    \b
    Examples:
      iris config schema product
      iris config schema taxonomy -o docs/schemas/taxonomy.schema.json
      iris config schema extraction -o docs/schemas/extraction.schema.json
    """
    json_schema = json.dumps(_SCHEMA_MODELS[model].model_json_schema(), indent=2)
    if output is None:
        click.echo(json_schema)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_schema + "\n", encoding="utf-8")
        click.echo(f"Written to {output}")
