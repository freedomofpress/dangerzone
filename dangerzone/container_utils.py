import logging
import platform
import shutil
import subprocess
from typing import List, Tuple

from . import errors
from .settings import Settings
from .util import get_resource_path, get_subprocess_startupinfo

CONTAINER_NAME = "dangerzone.rocks/dangerzone"

log = logging.getLogger(__name__)


def get_runtime_name() -> str:
    settings = Settings()
    try:
        runtime_name = settings.get("container_runtime")
    except KeyError:
        return "podman" if platform.system() == "Linux" else "docker"
    return runtime_name


def get_runtime() -> str:
    container_tech = get_runtime_name()
    runtime = shutil.which(container_tech)
    if runtime is None:
        raise errors.NoContainerTechException(container_tech)
    return runtime


def get_runtime_version() -> Tuple[int, int]:
    """Get the major/minor parts of the Docker/Podman version.

    Some of the operations we perform in this module rely on some Podman features
    that are not available across all of our platforms. In order to have a proper
    fallback, we need to know the Podman version. More specifically, we're fine with
    just knowing the major and minor version, since writing/installing a full-blown
    semver parser is an overkill.
    """
    # Get the Docker/Podman version, using a Go template.
    runtime_name = get_runtime_name()

    if runtime_name == "podman":
        query = "{{.Client.Version}}"
    else:
        query = "{{.Server.Version}}"

    cmd = [get_runtime(), "version", "-f", query]
    try:
        version = subprocess.run(
            cmd,
            startupinfo=get_subprocess_startupinfo(),
            capture_output=True,
            check=True,
        ).stdout.decode()
    except Exception as e:
        msg = f"Could not get the version of the {runtime.name.capitalize()} tool: {e}"
        raise RuntimeError(msg) from e

    # Parse this version and return the major/minor parts, since we don't need the
    # rest.
    try:
        major, minor, _ = version.split(".", 3)
        return (int(major), int(minor))
    except Exception as e:
        msg = (
            f"Could not parse the version of the {runtime_name.capitalize()} tool"
            f" (found: '{version}') due to the following error: {e}"
        )
        raise RuntimeError(msg)


def list_image_tags() -> List[str]:
    """Get the tags of all loaded Dangerzone images.

    This method returns a mapping of image tags to image IDs, for all Dangerzone
    images. This can be useful when we want to find which are the local image tags,
    and which image ID does the "latest" tag point to.
    """
    return (
        subprocess.check_output(
            [
                get_runtime(),
                "image",
                "list",
                "--format",
                "{{ .Tag }}",
                CONTAINER_NAME,
            ],
            text=True,
            startupinfo=get_subprocess_startupinfo(),
        )
        .strip()
        .split()
    )


def add_image_tag(image_id: str, new_tag: str) -> None:
    """Add a tag to the Dangerzone image."""
    log.debug(f"Adding tag '{new_tag}' to image '{image_id}'")
    subprocess.check_output(
        [get_runtime(), "tag", image_id, new_tag],
        startupinfo=get_subprocess_startupinfo(),
    )


def delete_image_tag(tag: str) -> None:
    """Delete a Dangerzone image tag."""
    log.warning(f"Deleting old container image: {tag}")
    try:
        subprocess.check_output(
            [get_runtime(), "rmi", "--force", tag],
            startupinfo=get_subprocess_startupinfo(),
        )
    except Exception as e:
        log.warning(
            f"Couldn't delete old container image '{tag}', so leaving it there."
            f" Original error: {e}"
        )


def get_expected_tag() -> str:
    """Get the tag of the Dangerzone image tarball from the image-id.txt file."""
    with get_resource_path("image-id.txt").open() as f:
        return f.read().strip()


def load_image_tarball() -> None:
    log.info("Installing Dangerzone container image...")
    tarball_path = get_resource_path("container.tar")
    try:
        res = subprocess.run(
            [get_runtime(), "load", "-i", str(tarball_path)],
            startupinfo=get_subprocess_startupinfo(),
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr:
            error = e.stderr.decode()
        else:
            error = "No output"
        raise errors.ImageInstallationException(
            f"Could not install container image: {error}"
        )

    # Loading an image built with Buildkit in Podman 3.4 messes up its name. The tag
    # somehow becomes the name of the loaded image [1].
    #
    # We know that older Podman versions are not generally affected, since Podman v3.0.1
    # on Debian Bullseye works properly. Also, Podman v4.0 is not affected, so it makes
    # sense to target only Podman v3.4 for a fix.
    #
    # The fix is simple, tag the image properly based on the expected tag from
    # `share/image-id.txt` and delete the incorrect tag.
    #
    # [1] https://github.com/containers/podman/issues/16490
    if get_runtime_name() == "podman" and get_runtime_version() == (3, 4):
        expected_tag = get_expected_tag()
        bad_tag = f"localhost/{expected_tag}:latest"
        good_tag = f"{CONTAINER_NAME}:{expected_tag}"

        log.debug(
            f"Dangerzone images loaded in Podman v3.4 usually have an invalid tag."
            " Fixing it..."
        )
        add_image_tag(bad_tag, good_tag)
        delete_image_tag(bad_tag)

    log.info("Successfully installed container image")
