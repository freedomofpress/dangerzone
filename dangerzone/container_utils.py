import functools
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import IO, Callable, Iterable, List, Optional, Tuple, Union

from dangerzone.podman.errors.exceptions import PodmanNotInstalled

from . import errors
from .podman.command import PodmanCommand
from .settings import Settings
from .util import (
    get_cache_dir,
    get_resource_path,
    get_subprocess_startupinfo,
    get_version,
)

# Keep the name of the old container here to be able to get rid of it later
OLD_CONTAINER_NAME = "dangerzone.rocks/dangerzone"
CONTAINER_PREFIX = "dangerzone-"
CONTAINERS_CONF_PATH = get_cache_dir() / "containers.conf"
SECCOMP_PATH = get_cache_dir() / "shared" / "seccomp.gvisor.json"
PODMAN_MACHINE_PREFIX = "dz-internal-"
PODMAN_MACHINE_NAME = f"{PODMAN_MACHINE_PREFIX}{get_version()}"
TIMEOUT_KILL = 5  # Timeout in seconds until the kill command returns.

log = logging.getLogger(__name__)


# subprocess.run with the correct startupinfo for Windows.
# We use a partial here to better profit from type checking
subprocess_run = functools.partial(
    subprocess.run, startupinfo=get_subprocess_startupinfo()
)


def get_runtime_version() -> Tuple[int, int]:
    """Get the major/minor parts of the Docker/Podman version.

    Some of the operations we perform in this module rely on some Podman features
    that are not available across all of our platforms. In order to have a proper
    fallback, we need to know the Podman version. More specifically, we're fine with
    just knowing the major and minor version, since writing/installing a full-blown
    semver parser is an overkill.
    """
    # Get the Docker/Podman version, using a Go template.
    podman = init_podman_command()
    query = "{{.Client.Version}}"

    try:
        version = podman.run(["version", "-f", query])
        assert isinstance(version, str)
    except Exception as e:
        msg = f"Could not get the version of Podman: {e}"
        raise RuntimeError(msg) from e

    # Parse this version and return the major/minor parts, since we don't need the
    # rest.
    try:
        major, minor, _ = version.split(".", 3)
        return (int(major), int(minor))
    except Exception as e:
        msg = (
            f"Could not parse the version of Podman (found: '{version}') due to the"
            f" following error: {e}"
        )
        raise RuntimeError(msg)


def get_podman_path() -> Optional[Path]:
    podman_bin = "podman"
    if platform.system() == "Linux":
        return None  # Use default Podman location
    elif platform.system() == "Windows":
        podman_bin += ".exe"
    return get_resource_path("vendor") / "podman" / podman_bin


def make_seccomp_json_accessible() -> Union[Path, PurePosixPath]:
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
    if get_runtime_version() < (4, 0):
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

    if platform.system() == "Linux":
        return src
    else:
        SECCOMP_PATH.parent.mkdir(parents=True, exist_ok=True)
        # This file will be overwritten on every conversion, which is unnecessary, but
        # the copy operation should be quick.
        shutil.copy(src, SECCOMP_PATH)
        if platform.system() == "Windows":
            # Translate the Windows path on the host to the WSL2 path on the VM. That
            # is, change backslashes to forward slashes, and replace 'C:/' with
            # '/mnt/c'.
            subpath = SECCOMP_PATH.relative_to("C:\\").as_posix()
            return PurePosixPath("/mnt/c") / subpath
        return SECCOMP_PATH


def create_containers_conf() -> Path:
    # Determine path of vendored Podman helpers.
    #
    # We cannot simply use the vendored Podman binary in order to start a Podman
    # machine, because it needs to use some other utilities as well (vfkit, gvproxy).
    # Since we can't install these utilities in $PATH, we have to pass them via the
    # `helper_binaries_dir` config option. Read more about this field in this section:
    # https://github.com/containers/common/blob/main/docs/containers.conf.5.md#engine-table
    podman_path = get_podman_path()
    assert isinstance(podman_path, Path)
    helper_binaries_dir = str(podman_path.parent)
    helper_binaries_dir = helper_binaries_dir.replace("\\", "\\\\")

    # Determine volumes of Podman machine.
    #
    # By default, Podman machines boot with a permissive view of the host's filesystem.
    # We want to limit this access as much as possible using the `volumes` config
    # option, and specifically mounting only the seccomp policy file as read-only.
    #
    # Note that the following option does not affect Windows users, because WSL2 will
    # always mount C: into the VM. Read more in:
    # https://github.com/freedomofpress/dangerzone/issues/1171#issuecomment-3279044187
    volume = f"{SECCOMP_PATH.parent}:{SECCOMP_PATH.parent}:ro"
    volume = volume.replace("\\", "\\\\")
    SECCOMP_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Determine CPU count.
    #
    # Because the Podman machine is short-lived, we can employ more CPU cores than the
    # default for the duration of the conversion.
    cpu_count = os.cpu_count() or 1

    content = f"""\
[engine]
helper_binaries_dir=["{helper_binaries_dir}"]

[machine]
cpus={cpu_count}
volumes=["{volume}"]
"""
    # FIXME: Do not unconditionally write to this file.
    dst = CONTAINERS_CONF_PATH
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content)
    return dst


@functools.cache
def init_podman_command() -> PodmanCommand:
    podman_path: Optional[Path]
    settings = Settings()

    if settings.custom_runtime_specified():
        podman_path = Path(settings.get("container_runtime"))
        if not podman_path.exists():
            raise errors.UnsupportedContainerRuntime(podman_path)
    else:
        podman_path = get_podman_path()

    options = env = None
    if platform.system() != "Linux" and not settings.custom_runtime_specified():
        env = os.environ.copy()
        env["CONTAINERS_CONF"] = str(create_containers_conf())
        options = PodmanCommand.GlobalOptions(connection=PODMAN_MACHINE_NAME)
        if settings.debug:
            options.log_level = "debug"

    try:
        return PodmanCommand(path=podman_path, env=env, options=options)
    except PodmanNotInstalled:
        if getattr(sys, "dangerzone_dev", False):
            raise errors.ContainerException(
                "It seems that Podman is not present in your development environment."
                " You can run `mazette install` to download and install it."
                f" Expected path: {podman_path}"
            )
        else:
            raise errors.ContainerException(
                "Dangerzone could not find the Podman binary locally, which"
                " is necessary to start containers. This binary should be included as"
                " part of the installation, so the fact that it's missing indicates"
                " that your installation may be broken. You can try reinstalling"
                " Dangerzone, but if the problem persists, please contact us."
            )


def list_image_digests() -> List[str]:
    """Get the digests of all loaded Dangerzone images."""
    podman = init_podman_command()
    return (
        podman.run(
            [
                "image",
                "list",
                "--format",
                "{{ .Digest }}",
                expected_image_name(),
            ],
        )
        .strip()  # type: ignore [union-attr]
        .split()
    )


def list_containers() -> List[str]:
    """Get all the Dangerzone containers."""
    podman = init_podman_command()
    containers = (
        podman.run(
            [
                "ps",
                "-a",
                "--format",
                "{{ .Names }}",
            ],
        )
        .strip()  # type: ignore [union-attr]
        .split()
    )
    return [cont for cont in containers if cont.startswith(CONTAINER_PREFIX)]


def kill_container(name: str) -> None:
    """Terminate a spawned container."""
    podman = init_podman_command()
    try:
        # We do not check the exit code of the process here, since the container may
        # have stopped right before invoking this command. In that case, the
        # command's output will contain some error messages, so we capture them in
        # order to silence them.
        #
        # NOTE: We specify a timeout for this command, since we've seen it hang
        # indefinitely for specific files. See:
        # https://github.com/freedomofpress/dangerzone/issues/854
        podman.run(["kill", name], check=False, timeout=TIMEOUT_KILL)
    except subprocess.TimeoutExpired:
        log.warning(f"Could not kill container '{name}' within {TIMEOUT_KILL} seconds")
    except Exception as e:
        log.exception(
            f"Unexpected error occurred while killing container '{name}': {str(e)}"
        )


def add_image_tag(image_id: str, new_tag: str) -> None:
    """Add a tag to the Dangerzone image."""
    podman = init_podman_command()
    log.debug(f"Adding tag '{new_tag}' to image '{image_id}'")
    podman.run(
        ["tag", image_id, new_tag],
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
    podman = init_podman_command()
    log.warning(f"Deleting container images: {' '.join(full_digests)}")
    try:
        podman.run(["rmi", "--force", *full_digests])
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
    log.info("Installing Dangerzone container image...")
    podman = init_podman_command()
    if not tarball_path:
        tarball_path = get_resource_path("container.tar")
    try:
        res = podman.run(["load", "-i", str(tarball_path)])
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
    podman = init_podman_command()
    image_id = get_image_id_by_digest(digest)
    podman.run(["tag", image_id, tag])


def get_image_id_by_digest(digest: str) -> str:
    """Get an image ID from a digest.
    The sha256: prefix should be omitted from the digest.
    """
    # There is a "digest" filter that you can use with
    # "podman images -f digest:<digest>", but it's only available
    # for podman >=4.4 (and bookworm ships 4.3)
    # So, fallback on the json format instead
    podman = init_podman_command()
    res = podman.run(["images", "--format", "json"])
    assert isinstance(res, str)
    images = json.loads(res)
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
    podman = init_podman_command()
    process = podman.run(
        ["pull", f"{image}@sha256:{manifest_digest}"], wait=False, text=True, bufsize=1
    )
    assert isinstance(process, subprocess.Popen)

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
    # `podman images` returns the digest of the multi-architecture image,
    # which should match the downloaded signatures on a typical over-the-air
    # update scenario.
    # `podman inspect` is avoided here as it returns the digest of the
    # architecture-bound image.
    podman = init_podman_command()
    res = podman.run(["images", expected_image, "--format", "{{.Digest}}"])
    assert isinstance(res, str)
    # In some cases, the output can be multiple lines with the same digest
    # sets are used to reduce them.
    lines = set(res.split("\n"))
    if len(lines) < 1:
        raise errors.ImageNotPresentException(
            f"The image {expected_image} does not exist locally"
        )
    elif len(lines) > 1:
        raise errors.MultipleImagesFoundException(
            f"Expected a single line of output, got {len(lines)} lines: {lines}"
        )
    image_digest = lines.pop().replace("sha256:", "")
    return image_digest
