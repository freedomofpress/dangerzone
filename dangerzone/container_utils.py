import functools
import json
import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import IO, Callable, Iterable, List, Optional, Tuple

from . import errors
from .settings import Settings
from .util import get_resource_path, get_subprocess_startupinfo

# Keep the name of the old container here to be able to get rid of it later
OLD_CONTAINER_NAME = "dangerzone.rocks/dangerzone"

log = logging.getLogger(__name__)


class Runtime(object):
    """Represents the container runtime to use.

    - It can be specified via the settings, using the "container_runtime" key,
      which should point to the full path of the runtime;
    - If the runtime is not specified via the settings, it defaults
      to "podman" on Linux and "docker" on macOS and Windows.
    """

    def __init__(self) -> None:
        settings = Settings()

        if settings.custom_runtime_specified():
            self.path = Path(settings.get("container_runtime"))
            if not self.path.exists():
                raise errors.UnsupportedContainerRuntime(self.path)
            self.name = self.path.stem
        else:
            self.name = self.get_default_runtime_name()
            self.path = Runtime.path_from_name(self.name)

        if self.name not in ("podman", "docker"):
            raise errors.UnsupportedContainerRuntime(self.name)

    @staticmethod
    def path_from_name(name: str) -> Path:
        name_path = Path(name)
        if name_path.is_file():
            return name_path
        else:
            runtime = shutil.which(name_path)
            if runtime is None:
                raise errors.NoContainerTechException(name)
            return Path(runtime)

    @staticmethod
    def get_default_runtime_name() -> str:
        return "podman" if platform.system() == "Linux" else "docker"


# subprocess.run with the correct startupinfo for Windows.
# We use a partial here to better profit from type checking
subprocess_run = functools.partial(
    subprocess.run, startupinfo=get_subprocess_startupinfo()
)


def get_runtime_version(runtime: Optional[Runtime] = None) -> Tuple[int, int]:
    """Get the major/minor parts of the Docker/Podman version.

    Some of the operations we perform in this module rely on some Podman features
    that are not available across all of our platforms. In order to have a proper
    fallback, we need to know the Podman version. More specifically, we're fine with
    just knowing the major and minor version, since writing/installing a full-blown
    semver parser is an overkill.
    """
    runtime = runtime or Runtime()

    # Get the Docker/Podman version, using a Go template.
    if runtime.name == "podman":
        query = "{{.Client.Version}}"
    else:
        query = "{{.Server.Version}}"

    cmd = [str(runtime.path), "version", "-f", query]
    try:
        version = subprocess_run(
            cmd,
            capture_output=True,
            check=True,
        ).stdout.decode()  # type:ignore[attr-defined]
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
            f"Could not parse the version of the {runtime.name.capitalize()} tool"
            f" (found: '{version}') due to the following error: {e}"
        )
        raise RuntimeError(msg)


def list_image_digests() -> List[str]:
    """Get the digests of all loaded Dangerzone images."""
    runtime = Runtime()
    return (
        subprocess.check_output(
            [
                str(runtime.path),
                "image",
                "list",
                "--format",
                "{{ .Digest }}",
                expected_image_name(),
            ],
            text=True,
            startupinfo=get_subprocess_startupinfo(),
        )
        .strip()
        .split()
    )


def add_image_tag(image_id: str, new_tag: str) -> None:
    """Add a tag to the Dangerzone image."""
    runtime = Runtime()
    log.debug(f"Adding tag '{new_tag}' to image '{image_id}'")
    subprocess.check_output(
        [str(runtime.path), "tag", image_id, new_tag],
        startupinfo=get_subprocess_startupinfo(),
    )


def delete_image_digests(
    digests: Iterable[str], container_name: Optional[str] = None
) -> None:
    """Delete a Dangerzone image by its id."""
    container_name = container_name or expected_image_name()
    full_digests = [f"{container_name}@{digest}" for digest in digests]
    if not full_digests:
        log.debug("Skipping image digest deletion: nothing to remove")
        return
    runtime = Runtime()
    log.warning(f"Deleting container images: {' '.join(full_digests)}")
    try:
        subprocess.check_output(
            [str(runtime.path), "rmi", "--force", *full_digests],
            startupinfo=get_subprocess_startupinfo(),
        )
    except Exception as e:
        log.warning(
            f"Couldn't delete container images '{' '.join(full_digests)}', so leaving it there."
            f" Original error: {e}"
        )


def clear_old_images(digest_to_keep: str) -> None:
    log.debug(f"Digest to keep: {digest_to_keep}")
    digests = list_image_digests()
    log.debug(f"Digests installed: {digests}")
    to_remove = filter(lambda x: x != f"sha256:{digest_to_keep}", digests)
    delete_image_digests(to_remove)


def load_image_tarball(tarball_path: Optional[Path] = None) -> None:
    runtime = Runtime()
    log.info("Installing Dangerzone container image...")
    if not tarball_path:
        tarball_path = get_resource_path("container.tar")
    try:
        res = subprocess_run(
            [str(runtime.path), "load", "-i", str(tarball_path)],
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


def tag_image_by_digest(digest: str, tag: str) -> None:
    """Tag a container image by digest.
    The sha256: prefix should be omitted from the digest.
    """
    runtime = Runtime()
    image_id = get_image_id_by_digest(digest)
    cmd = [str(runtime.path), "tag", image_id, tag]
    log.debug(" ".join(cmd))
    subprocess_run(cmd, check=True)


def get_image_id_by_digest(digest: str) -> str:
    """Get an image ID from a digest.
    The sha256: prefix should be omitted from the digest.
    """
    runtime = Runtime()
    # There is a "digest" filter that you can use with
    # "podman images -f digest:<digest>", but it's only available
    # for podman >=4.4 (and bookworm ships 4.3)
    # So, fallback on the json format instead
    cmd = [
        str(runtime.path),
        "images",
        "--format",
        "json",
    ]
    log.debug(" ".join(cmd))
    process = subprocess_run(cmd, check=True, capture_output=True)

    images = json.loads(process.stdout.decode().strip())  # type:ignore[attr-defined]
    filtered_images = [
        image["Id"] for image in images if image["Digest"] == f"sha256:{digest}"
    ]

    if not filtered_images:
        raise errors.ImageNotPresentException(
            f"Unable to find an image with digest {digest}"
        )
    return filtered_images[0]


def expected_image_name() -> str:
    image_name_path = get_resource_path("image-name.txt")
    return image_name_path.read_text().strip("\n")


def container_pull(
    image: str, manifest_digest: str, callback: Optional[Callable] = None
) -> None:
    """Pull a container image from a registry."""
    runtime = Runtime()
    cmd = [str(runtime.path), "pull", f"{image}@sha256:{manifest_digest}"]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    if callback:
        for line in process.stdout:  # type: ignore
            callback(line)

    process.wait()
    if process.returncode != 0:
        raise errors.ContainerPullException(
            f"Could not pull the container image: {process.returncode}"
        )


def get_local_image_digest(image: Optional[str] = None) -> str:
    """
    Returns a image hash from a local image name
    """
    expected_image = image or expected_image_name()
    # Get the image hash from the "podman images" command.
    # It's not possible to use "podman inspect" here as it
    # returns the digest of the architecture-bound image
    runtime = Runtime()
    cmd = [str(runtime.path), "images", expected_image, "--format", "{{.Digest}}"]
    log.debug(" ".join(cmd))
    try:
        result = subprocess_run(
            cmd,
            capture_output=True,
            check=True,
        )
        output = result.stdout.decode().strip().split("\n")  # type:ignore[attr-defined]
        # In some cases, the output can be multiple lines with the same digest
        # sets are used to reduce them.
        lines = set(output)
        if len(lines) != 1:
            raise errors.MultipleImagesFoundException(
                f"Expected a single line of output, got {len(lines)} lines: {lines}"
            )
        image_digest = lines.pop().replace("sha256:", "")
        if not image_digest:
            raise errors.ImageNotPresentException(
                f"The image {expected_image} does not exist locally"
            )
        return image_digest
    except subprocess.CalledProcessError as e:
        raise errors.ImageNotPresentException(
            f"The image {expected_image} does not exist locally"
        )
