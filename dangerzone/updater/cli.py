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
@click.argument("image", default=DEFAULT_IMAGE_NAME)
@click.option("--pubkey", default=signatures.DEFAULT_PUBKEY_LOCATION)
def upgrade(image: str, pubkey: str) -> None:
    """Upgrade the image to the latest signed version."""
    manifest_digest = registry.get_manifest_digest(image)
    try:
        is_upgraded = signatures.upgrade_container_image(image, manifest_digest, pubkey)
        if is_upgraded:
            click.echo(f"✅ The local image {image} has been upgraded")
            click.echo(f"✅ The image has been signed with {pubkey}")
            click.echo(f"✅ Signatures has been verified and stored locally")

    except errors.ImageAlreadyUpToDate as e:
        click.echo(f"✅ {e}")
        raise click.Abort()


@main.command()
@click.argument("image_filename")
@click.option("--pubkey", default=signatures.DEFAULT_PUBKEY_LOCATION)
def load_archive(image_filename: str, pubkey: str) -> None:
    """Upgrade the local image to the one in the archive."""
    try:
        loaded_image = signatures.upgrade_container_image_airgapped(
            image_filename, pubkey
        )
        click.echo(
            f"✅ Installed image {image_filename} on the system as {loaded_image}"
        )
    except errors.ImageAlreadyUpToDate as e:
        click.echo(f"✅ {e}")
        raise click.Abort()


@main.command()
@click.argument("image")
@click.option("--output", default="dangerzone-airgapped.tar")
def prepare_archive(image: str, output: str) -> None:
    """Prepare an archive to upgrade the dangerzone image on an airgapped environment."""
    signatures.prepare_airgapped_archive(image, output)
    click.echo(f"✅ Archive {output} created")


@main.command()
@click.argument("image", default=DEFAULT_IMAGE_NAME)
@click.option("--pubkey", default=signatures.DEFAULT_PUBKEY_LOCATION)
def verify_local(image: str, pubkey: str) -> None:
    """
    Verify the local image signature against a public key and the stored signatures.
    """
    # XXX remove a potentiel :tag
    if signatures.verify_local_image(image, pubkey):
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
    """List the tags available for a given image."""
    click.echo(f"Existing tags for {image}")
    for tag in registry.list_tags(image):
        click.echo(tag)


@main.command()
@click.argument("image")
def get_manifest(image: str) -> None:
    """Retrieves a remove manifest for a given image and displays it."""
    click.echo(registry.get_manifest(image))


@main.command()
@click.argument("image_name")
# XXX: Do we really want to check against this?
@click.option(
    "--branch",
    default=DEFAULT_BRANCH,
    help="The Git branch that the image was built from",
)
@click.option(
    "--commit",
    required=True,
    help="The Git commit the image was built from",
)
@click.option(
    "--repository",
    default=DEFAULT_REPOSITORY,
    help="The github repository to check the attestation for",
)
@click.option(
    "--workflow",
    default=".github/workflows/multi_arch_build.yml",
    help="The path of the GitHub actions workflow this image was created from",
)
def attest_provenance(
    image_name: str,
    branch: str,
    commit: str,
    repository: str,
    workflow: str,
) -> None:
    """
    Look up the image attestation to see if the image has been built
    on Github runners, and from a given repository.
    """
    # TODO: Parse image and make sure it has a tag. Might even check for a digest.
    # parsed = registry.parse_image_location(image)

    verified = attestations.verify(image_name, branch, commit, repository, workflow)
    if verified:
        click.echo(
            f"🎉 Successfully verified image '{image_name}' and its associated claims:"
        )
        click.echo(f"- ✅ SLSA Level 3 provenance")
        click.echo(f"- ✅ GitHub repo: {repository}")
        click.echo(f"- ✅ GitHub actions workflow: {workflow}")
        click.echo(f"- ✅ Git branch: {branch}")
        click.echo(f"- ✅ Git commit: {commit}")


if __name__ == "__main__":
    main()
