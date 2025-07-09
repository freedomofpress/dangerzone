import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple, Union

from . import errors
from .settings import Settings
from .util import get_cache_dir, get_resource_path, get_subprocess_startupinfo

CONTAINER_NAME = "dangerzone.rocks/dangerzone"

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
            f"Could not parse the version of the {runtime.name.capitalize()} tool"
            f" (found: '{version}') due to the following error: {e}"
        )
        raise RuntimeError(msg)


def make_seccomp_json_accessible(runtime: Runtime) -> Union[Path, PurePosixPath]:
    """Ensure that the bundled seccomp profile is accessible by the runtime.

    On Linux platforms, this method is basically a no-op since there's no VM
    involved.

    If the container runtime is Docker Desktop, then this method is a no-op as well,
    because it knows how to pass this file to the VM.

    If the container runtime is Podman on Windows/macOS, then we need to copy the
    file to a place where it will be mounted in the Podman machine. Typically, the
    user directory is mounted in the VM [1], so we opt to copy the seccomp profile to
    the cache dir for Dangerzone, which is within the user directory.

    For Windows, we have to be extra careful and translate the file path to the
    equivalent in the WSL2 VM [2].

    [1] https://github.com/containers/podman/issues/26558
    [2] Read about the 'volumes=' config in
        https://github.com/containers/common/blob/main/docs/containers.conf.5.md#machine-table
    """
    if runtime.name == "podman" and get_runtime_version(runtime) < (4, 0):
        # On OSes that use:
        #
        # * crun < 0.19
        # * runc < 1.0.0-rc95
        # * golang-github-containers-common [0] < v0.40.0
        #
        # the "mseal" system call _may_ be denied with ENOPERM, rather than the
        # expected ENOSYS, making the conversions fail [1].
        #
        # Currently, we are aware that the affected OSes are Debian Bullseye and Ubuntu
        # Jammy. Since it's not easy to test for every version of the above packages, we
        # choose a simpler heuristic to check if Podman is _potentially_ affected. If
        # the Podman version is >= 4.0, which was released 6 months after these
        # versions, in all likelihood it's not affected. Podman versions prior to 4.0
        # _may_ be affected, and currently include only Debian Bullseye and Ubuntu
        # Jammy.
        #
        # For affected Podman versions, we use a separate seccomp policy to allow
        # unknown syscalls, so that the kernel can fail them with ENOSYS.
        #
        # [0] https://github.com/containers/common/
        # [1] For more information, have a look at
        #     https://github.com/freedomofpress/dangerzone/issues/1201
        src = get_resource_path("seccomp.gvisor.permissive.json")
    else:
        src = get_resource_path("seccomp.gvisor.json")

    if platform.system() == "Linux" or runtime.name == "docker":
        return src
    elif runtime.name == "podman":
        dst = get_cache_dir() / "seccomp.gvisor.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        # This file will be overwritten on every conversion, which is unnecessary, but
        # the copy operation should be quick.
        shutil.copy(src, dst)
        if platform.system() == "Windows":
            # Translate the Windows path on the host to the WSL2 path on the VM. That
            # is, change backslashes to forward slashes, and replace 'C:/' with
            # '/mnt/c'.
            subpath = dst.relative_to("C:\\").as_posix()
            return PurePosixPath("/mnt/c") / subpath
        return dst
    else:
        # Amusingly, that's an actual runtime error...
        raise RuntimeError(f"Unexpected runtime: '{runtime.name}'")


def list_image_tags() -> List[str]:
    """Get the tags of all loaded Dangerzone images.

    This method returns a mapping of image tags to image IDs, for all Dangerzone
    images. This can be useful when we want to find which are the local image tags,
    and which image ID does the "latest" tag point to.
    """
    runtime = Runtime()
    return (
        subprocess.check_output(
            [
                str(runtime.path),
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
    runtime = Runtime()
    log.debug(f"Adding tag '{new_tag}' to image '{image_id}'")
    subprocess.check_output(
        [str(runtime.path), "tag", image_id, new_tag],
        startupinfo=get_subprocess_startupinfo(),
    )


def delete_image_tag(tag: str) -> None:
    """Delete a Dangerzone image tag."""
    runtime = Runtime()
    log.warning(f"Deleting old container image: {tag}")
    try:
        subprocess.check_output(
            [str(runtime.name), "rmi", "--force", tag],
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
    runtime = Runtime()
    log.info("Installing Dangerzone container image...")
    tarball_path = get_resource_path("container.tar")
    try:
        res = subprocess.run(
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
    if runtime.name == "podman" and get_runtime_version(runtime) == (3, 4):
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
