#!/usr/bin/python

import functools
import logging
from pathlib import Path

import click

from .. import container_utils
from ..container_utils import Runtime, expected_image_name
from ..util import get_architecture
from . import cosign, errors, log, registry, signatures
from .signatures import DEFAULT_PUBKEY_LOCATION

DEFAULT_REPOSITORY = "freedomofpress/dangerzone"
DEFAULT_BRANCH = "main"
DEFAULT_IMAGE_NAME = expected_image_name()


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
def upgrade() -> None:
    """Upgrade the image to the latest version (only if it is signed).

    It is not possible to upgrade to a different image than the one
    specified in share/image-name.txt using this CLI invocation.

    If you want to do so, please use "prepare-archive" and "load-archive"
    instead.
    """
    manifest_digest = registry.get_manifest_digest(DEFAULT_IMAGE_NAME)

    try:
        callback = functools.partial(click.echo, nl=False)
        signatures.upgrade_container_image(
            manifest_digest, DEFAULT_IMAGE_NAME, callback=callback
        )
        click.echo(f"✅ The local image {DEFAULT_IMAGE_NAME} has been upgraded")
        click.echo(f"✅ The image has been signed with {DEFAULT_PUBKEY_LOCATION}")
        click.echo(f"✅ Signatures have been verified and stored locally")

    except errors.ImageAlreadyUpToDate as e:
        click.echo(f"✅ {e}")
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ {e}")
        raise click.Abort()


@main.command()
@click.argument("image", default=DEFAULT_IMAGE_NAME)
def store_signatures(image: str) -> None:
    manifest_digest = registry.get_manifest_digest(image)
    sigs = signatures.get_remote_signatures(image, manifest_digest)
    signatures.verify_signatures(sigs, manifest_digest)
    signatures.store_signatures(sigs, manifest_digest, update_logindex=False)
    click.echo(f"✅ Signatures have been verified and stored locally")


@main.command()
@click.argument("archive_filename", type=click.Path(exists=True))
@click.option("--force", is_flag=True)
def load_archive(archive_filename: Path, force: bool) -> None:
    """Upgrade the local image to the one in the archive."""
    try:
        loaded_image = signatures.upgrade_container_image_airgapped(
            archive_filename, bypass_logindex=force
        )
        click.echo(
            f"✅ Installed image {archive_filename} on the system as {loaded_image}"
        )
    except errors.ImageAlreadyUpToDate as e:
        click.echo(f"✅ {e}")
    except errors.InvalidLogIndex as e:
        click.echo("❌ Trying to install image older that the currently installed one")
        raise click.Abort()
    except errors.SignatureError as e:
        click.echo(f"❌ Failed to verify the signatures.")
        raise click.Abort()


@main.command()
@click.option("--image", default=DEFAULT_IMAGE_NAME)
@click.option("--output", default="dangerzone-{arch}.tar")
@click.option(
    "--arch",
    default=get_architecture(),
    help="The architecture you want to prepare the archive for. By default, it uses your platform.",
)
def prepare_archive(image: str, output: str, arch: str) -> None:
    """Prepare an archive to upgrade the dangerzone image (useful for airgapped environment)"""
    archive = output.format(arch=arch)
    try:
        signatures.prepare_airgapped_archive(image, archive, arch)
        click.echo(f"✅ Archive {archive} created")
    except errors.SignatureError:
        click.echo("❌ Failed to verify the signatures.")
        raise click.Abort()


@main.command()
@click.argument("image", default=DEFAULT_IMAGE_NAME)
def verify_local(image: str, pubkey: Path) -> None:
    """
    Verify the local image signature against a public key and the stored signatures.
    """
    if signatures.verify_local_image(image):
        click.echo(
            (
                f"Verifying the local image:\n\n"
                f"pubkey: {DEFAULT_PUBKEY_LOCATION}\n"
                f"image: {image}\n\n"
                f"✅ The local image {image} has been signed with the public key"
            )
        )


@main.command()
@click.argument("image_name")
@click.option(
    "--branch",
    default=DEFAULT_BRANCH,
    help="The Git branch that the image was built from",
)
@click.option(
    "--commit",
    required=True,
    help="The full Git commit the image was built from",
)
@click.option(
    "--repository",
    default=DEFAULT_REPOSITORY,
    help="The github repository to check the attestation for",
)
@click.option(
    "--workflow",
    default=".github/workflows/release-container-image.yml",
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

    verified = cosign.verify_attestation(
        image_name, branch, commit, repository, workflow
    )
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
