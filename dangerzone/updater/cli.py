#!/usr/bin/python

import click

from . import registry
from .attestations import verify_attestation
from .signatures import upgrade_container_image, verify_offline_image_signature

DEFAULT_REPO = "freedomofpress/dangerzone"


@click.group()
def main():
    pass


@main.command()
@click.argument("image")
@click.option("--pubkey", default="pub.key")
# XXX Add options to do airgap upgrade
def upgrade(image, pubkey):
    manifest_hash = registry.get_manifest_hash(image)
    if upgrade_container_image(image, manifest_hash, pubkey):
        click.echo(f"✅ The local image {image} has been upgraded")


@main.command()
@click.argument("image")
@click.option("--pubkey", default="pub.key")
def verify_local(image, pubkey):
    """
    XXX document
    """
    # XXX remove a potentiel :tag
    if verify_offline_image_signature(image, pubkey):
        click.echo(f"✅ The local image {image} has been signed with {pubkey}")


@main.command()
@click.argument("image")
def list_tags(image):
    click.echo(f"Existing tags for {client.image}")
    for tag in registry.list_tags(image):
        click.echo(tag)


@main.command()
@click.argument("image")
@click.argument("tag")
def get_manifest(image, tag):
    click.echo(registry.get_manifest(image, tag))


@main.command()
@click.argument("image")
@click.option(
    "--repo",
    default=DEFAULT_REPO,
    help="The github repository to check the attestation for",
)
# XXX use a consistent naming for these cli commands
def attest(image: str, repo: str):
    """
    Look up the image attestation to see if the image has been built
    on Github runners, and from a given repository.
    """
    # XXX put this inside a module
    # if shutil.which("cosign") is None:
    #     click.echo("The cosign binary is needed but not installed.")
    #     raise click.Abort()
    # XXX: refactor parse_image_location to return a dict.
    _, _, _, image_tag = registry.parse_image_location(image)
    manifest, bundle = registry.get_attestation(image)

    verified = verify_attestation(manifest, bundle, image_tag, repo)
    if verified:
        click.echo(
            f"🎉 The image available at `{client.image}:{image_tag}` has been built by Github Runners from the `{repo}` repository"
        )


if __name__ == "__main__":
    main()
