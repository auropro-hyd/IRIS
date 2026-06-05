"""IRIS command-line interface."""

import click

from iris_cli.commands.config import config


@click.group()
def iris() -> None:
    """IRIS: Insurance Reference Intelligence Stack."""


iris.add_command(config)
