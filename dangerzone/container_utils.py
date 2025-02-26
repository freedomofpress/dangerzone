import logging
import platform
import shutil
import subprocess
from typing import List, Tuple

from . import errors
from .util import get_resource_path, get_subprocess_startupinfo

CONTAINER_NAME = "dangerzone.rocks/dangerzone"

log = logging.getLogger(__name__)


def get_runtime_name() -> str:
    if platform.system() == "Linux":
        runtime_name = "podman"
    else:
        # Windows, Darwin, and unknown use docker for now, dangerzone-vm eventually
        runtime_name = "docker"
    return runtime_name


def get_runtime_version() -> Tuple[int, int]:
    """Get the major/minor parts of the Docker/Podman version.

    Some of the operations we perform in this module rely on some Podman features
    that are not available across all of our platforms. In order to have a proper
    fallback, we need to know the Podman version. More specifically, we're fine with
    just knowing the major and minor version, since writing/installing a full-blown
    semver parser is an overkill.
    """
    # Get the Docker/Podman version, using a Go template.
    runtime = get_runtime_name()
    if runtime == "podman":
        query = "{{.Client.Version}}"
    else:
        query = "{{.Server.Version}}"

    cmd = [runtime, "version", "-f", query]
    try:
        version = subprocess.run(
            cmd,
            startupinfo=get_subprocess_startupinfo(),
            capture_output=True,
            check=True,
        ).stdout.decode()
    except Exception as e:
        msg = f"Could not get the version of the {runtime.capitalize()} tool: {e}"
        raise RuntimeError(msg) from e

    # Parse this version and return the major/minor parts, since we don't need the
    # rest.
    try:
        major, minor, _ = version.split(".", 3)
        return (int(major), int(minor))
    except Exception as e:
        msg = (
            f"Could not parse the version of the {runtime.capitalize()} tool"
            f" (found: '{version}') due to the following error: {e}"
        )
        raise RuntimeError(msg)


def get_runtime() -> str:
    container_tech = get_runtime_name()
    runtime = shutil.which(container_tech)
    if runtime is None:
        raise errors.NoContainerTechException(container_tech)
    return runtime


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


def delete_image_tag(tag: str) -> None:
    """Delete a Dangerzone image tag."""
    name = CONTAINER_NAME + ":" + tag
    log.warning(f"Deleting old container image: {name}")
    try:
        subprocess.check_output(
            [get_runtime(), "rmi", "--force", name],
            startupinfo=get_subprocess_startupinfo(),
        )
    except Exception as e:
        log.warning(
            f"Couldn't delete old container image '{name}', so leaving it there."
            f" Original error: {e}"
        )


def get_expected_tag() -> str:
    """Get the tag of the Dangerzone image tarball from the image-id.txt file."""
    with open(get_resource_path("image-id.txt")) as f:
        return f.read().strip()


def load_image_tarball() -> None:
    log.info("Installing Dangerzone container image...")
    tarball_path = get_resource_path("container.tar")
    with open(tarball_path) as f:
        try:
            subprocess.run(
                [get_runtime(), "load"],
                stdin=f,
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

    log.info("Successfully installed container image")
