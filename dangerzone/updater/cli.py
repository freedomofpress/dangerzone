#!/usr/bin/python

import logging

import click

from ..util import get_resource_path
from . import errors, log, registry
from .attestations import verify_attestation
from .signatures import (
    upgrade_container_image,
    upgrade_container_image_airgapped,
    verify_offline_image_signature,
)

DEFAULT_REPOSITORY = "freedomofpress/dangerzone"
DEFAULT_IMAGE_NAME = "ghcr.io/freedomofpress/dangerzone"
PUBKEY_DEFAULT_LOCATION = get_resource_path("freedomofpress-dangerzone-pub.key")


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
@click.option("--pubkey", default=PUBKEY_DEFAULT_LOCATION)
def upgrade(image: str, pubkey: str) -> None:
    """Upgrade the image to the latest signed version."""
    manifest_hash = registry.get_manifest_hash(image)
    try:
        is_upgraded = upgrade_container_image(image, manifest_hash, pubkey)
        click.echo(f"✅ The local image {image} has been upgraded")
    except errors.ImageAlreadyUpToDate as e:
        click.echo(f"✅ {e}")
        raise click.Abort()


@main.command()
@click.argument("image_filename")
@click.option("--pubkey", default=PUBKEY_DEFAULT_LOCATION)
@click.option("--image-name", default=DEFAULT_IMAGE_NAME)
def upgrade_airgapped(image_filename: str, pubkey: str, image_name: str) -> None:
    """Upgrade the image to the latest signed version."""
    try:
        upgrade_container_image_airgapped(image_filename, pubkey, image_name)
        click.echo(f"✅ Installed image {image_filename} on the system")
    except errors.ImageAlreadyUpToDate as e:
        click.echo(f"✅ {e}")
        raise click.Abort()


@main.command()
@click.argument("image")
@click.option("--pubkey", default=PUBKEY_DEFAULT_LOCATION)
def verify_offline(image: str, pubkey: str) -> None:
    """
    Verify the local image signature against a public key and the stored signatures.
    """
    # XXX remove a potentiel :tag
    if verify_offline_image_signature(image, pubkey):
        click.echo(
            (
                f"Verifying the local image:\n\n"
                f"pubkey: {pubkey}\n"
                f"image: {image}\n\n"
                f"✅ The local image {image} has been signed with {pubkey}"
            )
        )


@main.command()
@click.argument("image")
def list_remote_tags(image: str) -> None:
    click.echo(f"Existing tags for {image}")
    for tag in registry.list_tags(image):
        click.echo(tag)


@main.command()
@click.argument("image")
def get_manifest(image: str) -> None:
    click.echo(registry.get_manifest(image))


@main.command()
@click.argument("image")
@click.option(
    "--repository",
    default=DEFAULT_REPOSITORY,
    help="The github repository to check the attestation for",
)
def attest_provenance(image: str, repository: str) -> None:
    """
    Look up the image attestation to see if the image has been built
    on Github runners, and from a given repository.
    """
    # XXX put this inside a module
    # if shutil.which("cosign") is None:
    #     click.echo("The cosign binary is needed but not installed.")
    #     raise click.Abort()
    parsed = registry.parse_image_location(image)
    manifest, bundle = registry.get_attestation(image)

    verified = verify_attestation(manifest, bundle, parsed.tag, repository)
    if verified:
        click.echo(
            f"🎉 The image available at `{parsed.full_name}` has been built by Github Runners from the `{repository}` repository"
        )


if __name__ == "__main__":
    main()
