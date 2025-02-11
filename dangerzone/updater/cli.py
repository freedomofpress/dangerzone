#!/usr/bin/python

import logging

import click

from . import attestations, errors, log, registry, signatures

DEFAULT_REPOSITORY = "freedomofpress/dangerzone"
DEFAULT_BRANCH = "main"
DEFAULT_IMAGE_NAME = "ghcr.io/freedomofpress/dangerzone/dangerzone"


@click.group()
@click.option("--debug", is_flag=True)
def main(debug: bool) -> None:
    if debug:
        click.echo("Debug mode enabled")
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(level=level)


@main.command()
@click.argument("image")
def list_remote_tags(image: str) -> None:
    """List the tags available for a given image."""
    click.echo(f"Existing tags for {image}")
    for tag in registry.list_tags(image):
        click.echo(tag)


@main.command()
@click.argument("image")
def get_manifest(image: str) -> None:
    """Retrieves a remote manifest for a given image and displays it."""
    click.echo(registry.get_manifest(image).content)


if __name__ == "__main__":
    main()
