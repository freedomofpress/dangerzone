#!/usr/bin/python

import functools
import logging
import platform
from pathlib import Path
from typing import Any, Callable

import click

from .. import shutdown, startup
from ..container_utils import expected_image_name
from ..podman.machine import PodmanMachineManager
from ..util import get_architecture
from . import cosign, errors, log, registry, signatures
from .signatures import DEFAULT_PUBKEY_LOCATION

DEFAULT_REPOSITORY = "freedomofpress/dangerzone"
DEFAULT_BRANCH = "main"
DEFAULT_IMAGE_NAME = expected_image_name()


def requires_container_runtime(func: Callable) -> Callable:
    """Decorator to start and stop Podman machines for commands that require it."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        tasks = [
            startup.WSLInstallTask(),
            startup.MachineStopOthersTask(),
            startup.MachineInitTask(),
            startup.MachineStartTask(),
        ]
        try:
            startup.StartupLogic(tasks=tasks).run()
            res = func(*args, **kwargs)
        finally:
            shutdown.ShutdownLogic(tasks=[shutdown.MachineStopTask()]).run()
        return res

    return wrapper


@click.group(context_settings={"show_default": True})
@click.option("--debug", is_flag=True)
def run(debug: bool) -> None:
    if debug:
        click.echo("Debug mode enabled")
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(level=level)


@run.command()
@requires_container_runtime
def upgrade() -> None:
    """Upgrade the sandbox to the latest version available.

    To upgrade to a custom sandbox image, use "prepare-archive" and "load-archive"
    instead.
    """
    manifest_digest = registry.get_manifest_digest(DEFAULT_IMAGE_NAME)

    try:
        signatures.upgrade_container_image(manifest_digest, DEFAULT_IMAGE_NAME)
        click.echo(f"✅ The local image {DEFAULT_IMAGE_NAME} has been upgraded")
        click.echo(f"✅ The image has been signed with {DEFAULT_PUBKEY_LOCATION}")
        click.echo(f"✅ Signatures have been verified and stored locally")

    except errors.ImageAlreadyUpToDate as e:
        click.echo(
            f"✅ The local image {DEFAULT_IMAGE_NAME}@{manifest_digest} is already up to date"
        )
    except Exception as e:
        click.echo(f"❌ {e}")
        raise click.Abort()


@run.command()
@click.option(
    "--image",
    default=DEFAULT_IMAGE_NAME,
)
def store_signatures(image: str) -> None:
    """Retrieves and stores the signatures of the remote sandbox"""
    manifest_digest = registry.get_manifest_digest(image)
    sigs = signatures.get_remote_signatures(image, manifest_digest)
    signatures.verify_signatures(sigs, manifest_digest)
    signatures.store_signatures(sigs, manifest_digest, update_logindex=False)
    click.echo(f"✅ Signatures have been verified and stored locally")


@run.command()
@click.argument("archive_filename", type=click.Path(exists=True))
@click.option(
    "--force",
    is_flag=True,
    help="Force the installation, bypassing logindex verification checks",
)
@requires_container_runtime
def load_archive(archive_filename: Path, force: bool) -> None:
    """Use ARCHIVE_FILENAME as the dangerzone sandbox image"""
    try:
        loaded_image, image_digest = signatures.upgrade_container_image_airgapped(
            archive_filename, bypass_logindex=force
        )
        click.echo(
            f"✅ Installed image {archive_filename} on the system as {loaded_image}"
            f" with digest {image_digest}"
        )
    except errors.ImageAlreadyUpToDate as e:
        click.echo(f"✅ {e}")
    except errors.InvalidLogIndex as e:
        click.echo("❌ Trying to install image older that the currently installed one")
        raise click.Abort()
    except errors.SignatureError as e:
        click.echo(f"❌ Failed to verify the signatures.")
        raise click.Abort()


@run.command()
@click.option(
    "--image",
    default=DEFAULT_IMAGE_NAME,
    help="The sandbox container registry location",
)
@click.option(
    "--output",
    default="dangerzone-{arch}.tar",
    help=(
        "The location of the generated archive. '{arch}' will be replaced by "
        "the specified or detected architecture (see --arch)"
    ),
)
@click.option(
    "--arch",
    default=get_architecture(),
    help="The architecture to prepare the archive for.",
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


@run.command()
@click.option(
    "--image",
    default=DEFAULT_IMAGE_NAME,
    help="The name of the image to check signatures for",
)
@requires_container_runtime
def verify_local(image: str) -> None:
    """
    Ensures local image signature(s) match the embedded public key.
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


if __name__ == "__main__":
    run()
