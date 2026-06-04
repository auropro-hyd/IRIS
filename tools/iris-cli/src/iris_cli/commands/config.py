"""iris config — Product bundle configuration commands."""

import sys
from pathlib import Path

import click
from iris_config import ConfigLoadError, load_bundle, load_products


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
            slug = path.name
            load_bundle(path, slug)
            click.echo(f"OK  {slug}")
        else:
            registry = load_products(path)
            for slug in registry:
                click.echo(f"OK  {slug}")
    except ConfigLoadError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
