#!/usr/bin/python

import click

from . import registry
from .attestations import verify_attestation
from .signatures import upgrade_container_image, verify_offline_image_signature

DEFAULT_REPOSITORY = "freedomofpress/dangerzone"


@click.group()
def main() -> None:
    pass


@main.command()
@click.option("--image")
@click.option("--pubkey", default="pub.key")
@click.option("--airgap", is_flag=True)
# XXX Add options to do airgap upgrade
def upgrade(image: str, pubkey: str) -> None:
    manifest_hash = registry.get_manifest_hash(image)
    if upgrade_container_image(image, manifest_hash, pubkey):
        click.echo(f"✅ The local image {image} has been upgraded")


@main.command()
@click.argument("image")
@click.option("--pubkey", default="pub.key")
def verify_local(image: str, pubkey: str) -> None:
    """
    Verify the local image signature against a public key and the stored signatures.
    """
    # XXX remove a potentiel :tag
    if verify_offline_image_signature(image, pubkey):
        click.echo(f"✅ The local image {image} has been signed with {pubkey}")


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
