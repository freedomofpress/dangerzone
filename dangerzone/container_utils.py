import functools
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from dangerzone.podman.errors.exceptions import PodmanNotInstalled

from . import errors
from .podman.command import PodmanCommand
from .podman.errors import CommandError
from .settings import Settings
from .util import (
    get_cache_dir,
    get_resource_path,
    get_tails_socks_proxy,
    get_version,
    linux_system_is,
)

CONTAINER_PREFIX = "dangerzone-"
CONTAINERS_CONF_PATH = get_cache_dir() / "containers.conf"
SECCOMP_PATH = get_cache_dir() / "shared" / "seccomp.gvisor.json"
PODMAN_MACHINE_PREFIX = "dz-internal-"
PODMAN_MACHINE_NAME = f"{PODMAN_MACHINE_PREFIX}{get_version()}"
TIMEOUT_KILL = 5  # Timeout in seconds until the kill command returns.

log = logging.getLogger(__name__)


class Image:
    """A Pythonic representation of a container image.

    This class represents some main pieces of information for container images that
    Dangerzone is interested in:
    * Digests
    * Names (tags)
    * Image ID

    This representation is by no means complete, but that's not the end goal here. It's
    actually supposed to be broad, because we list all images that exist in a user's
    machine, and we don't have control over them.

    Finally, this info is sourced by `podman images --format json [image]`. This class
    parses the output of this command and adds its own logic, especially for Dangerzone
    images.
    """

    @staticmethod
    def extract_digest(digest: str):
        if "@" in digest:
            digest = digest.split("@")[1]

        if digest.startswith("sha256:"):
            return digest

        raise ValueError(f"Malformed image digest: {digest}")

    def __init__(self, image_info: dict):
        """Initialize this class from a dict representation of a container image.

        The `image_info` argument should be the result of `podman images --format json`
        for a **single** container image, loaded as a dict.
        """
        self.id = image_info["Id"]
        self.names = image_info["Names"]
        self._local_digest = image_info["Digest"]

        # Normally, the RepoDigests field is a list with the following format:
        #
        #   "RepoDigests": [
        #       "name1@sha256:hash1",
        #       "name2@sha256:hash1",
        #   ],
        #
        # In this class, we want to keep only the digest part.
        self._repo_digests = [
            self.extract_digest(digest) for digest in image_info["RepoDigests"]
        ]

        # Add all digests in a single list.
        self.digests = list(set([self._local_digest] + self._repo_digests))

    @classmethod
    def list(cls, image_filter: str | None = None):
        """Create a list of local images, optionally with a filter.

        Run `podman images --format json [image_filter]`, and return back a list of
        Image instances.
        """
        podman = init_podman_command()
        cmd = ["images", "--format", "json"]
        if image_filter:
            cmd.append(image_filter)

        res = podman.run(cmd)
        images = json.loads(res)
        return [cls(image_info) for image_info in images]

    @classmethod
    def list_dangerzone_images(cls):
        """Create a list of local Dangerzone images.

        List Dangerzone images by filtering with the expected image name. If we get no
        result back, raise `ImageNotPresentException`.
        """
        name = expected_image_name()
        images = cls.list(name)
        if not images:
            raise errors.ImageNotPresentException(
                f"The image {name} does not exist locally"
            )
        return images

    @classmethod
    def get_dangerzone_image(cls) -> "Image":
        """Get a single Dangerzone image.

        List Dangerzone images and expect that only one exists locally. If not, raise
        `MultipleImagesFoundException`.
        """
        images = cls.list_dangerzone_images()
        if len(images) > 1:
            raise errors.MultipleImagesFoundException(
                f"Expected a single Dangerzone image got {len(images)}: {images}"
            )
        return images[0]

    @classmethod
    def from_digest(cls, digest: str) -> "Image":
        """List all local images and return back one that matches a provided digest.

        If not found, raise `ImageNotPresentException`.
        """
        digest = normalize_digest(digest)
        images = [image for image in cls.list() if digest in image.digests]
        if not images:
            raise errors.ImageNotPresentException(
                f"Unable to find an image with digest {digest}"
            )
        # NOTE: Usually duplicate entries occur due to multiple names for the same
        # image. Still, we've seen that the image info is identical for both entries, so
        # we can return just the first result.
        return images[0]

    @property
    def is_dangerzone_image(self) -> bool:
        """Check if a container image matches the expected Dangerzone image name."""
        expected_name = expected_image_name()
        return any(name.startswith(expected_name) for name in self.names)

    # @property
    # def is_multi_arch(self) -> bool:
    #     """Check if a local container image is actually pulled from a multi-arch manifest.

    #     In Podman, the only way we can detect it
    #     """
    #     return len(self._repo_digests) > 1

    @property
    def platform_digest(self) -> bool:
        """Return the image digest for the platform of the user's machine.

        Attempt to return the digest that matches the platform of the user's machine,
        using some heuristics:
        * If a single digest is reported, then assume that this is the platform one.
        * If multiple digests are reported, then we make an assumption that works for
          Dangerzone images: the main digest is probably the multi-platform one, so the
          other repo digest is the platform one.

        NOTE: This is a bet, that works for now, but may stop working later, and
        definitely will not work for non-Dangerzone images.
        """
        if not self.is_dangerzone_image:
            raise RuntimeError("Expected a Dangerzone image")

        if len(self._repo_digests) > 2:
            raise RuntimeError("Too many digests")

        if len(self._repo_digests) == 2:
            platform_digest = set(self._repo_digests) - {self._local_digest}
            return next(iter(platform_digest))
        else:
            return self._local_digest

    def __repr__(self) -> str:
        return f"Image(id={self.id}, names={self.names}, digests={self.digests})"


def normalize_digest(digest: str) -> str:
    return digest if digest.startswith("sha256:") else "sha256:" + digest


def get_runtime_version() -> tuple[int, int]:
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
    except ValueError as e:
        msg = (
            f"Could not parse the version of Podman (found: '{version}') due to the"
            f" following error: {e}"
        )
        raise RuntimeError(msg)


def get_podman_path() -> Path | None:
    podman_bin = "podman"
    if platform.system() == "Linux":
        return None  # Use default Podman location
    elif platform.system() == "Windows":
        podman_bin += ".exe"
    return get_resource_path("vendor") / "podman" / podman_bin


def make_seccomp_json_accessible() -> Path | PurePosixPath:
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
        # Currently, we are aware that the affected OSes are Ubuntu Jammy.
        # Since it's not easy to test for every version of the above packages, we
        # choose a simpler heuristic to check if Podman is _potentially_ affected. If
        # the Podman version is >= 4.0, which was released 6 months after these
        # versions, in all likelihood it's not affected. Podman versions prior to 4.0
        # _may_ be affected, and currently include only Ubuntu Jammy.
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
rosetta=false
"""
    # FIXME: Do not unconditionally write to this file.
    dst = CONTAINERS_CONF_PATH
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content)
    return dst


@functools.cache
def init_podman_command() -> PodmanCommand:
    podman_path: Path | None
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
        options = PodmanCommand.GlobalOptions(
            connection=PODMAN_MACHINE_NAME,
            storage_opt="overlay.mount_program=/usr/bin/fuse-overlayfs",
        )
        if settings.debug:
            options.log_level = "debug"
    elif linux_system_is("Tails"):
        env = os.environ.copy()
        env["HTTPS_PROXY"] = get_tails_socks_proxy()
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


def list_containers() -> list[str]:
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
    except Exception:
        log.exception(f"Unexpected error occurred while killing container '{name}'")


def delete_image_digests(
    digests: Iterable[str], container_name: str | None = None
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
    except CommandError as e:
        log.warning(
            f"Couldn't delete container images '{' '.join(full_digests)}', so leaving it there."
            f" Original error: {e}"
        )


def clear_old_images(digest_to_keep: str) -> None:
    digest_to_keep = normalize_digest(digest_to_keep)
    log.debug(f"Digest to keep: {digest_to_keep}")

    images = Image.list_dangerzone_images()
    digests_to_remove = set()
    for image in images:
        if digest_to_keep not in image.digests:
            digests_to_remove |= set(image.digests)
    log.debug(f"Digests to remove: {digests_to_remove}")

    delete_image_digests(digests_to_remove)


def load_image_tarball(tarball_path: Path | None = None) -> str:
    """Load the image tarball, and return its digest."""
    log.info("Installing Dangerzone container image...")
    podman = init_podman_command()
    if not tarball_path:
        tarball_path = get_resource_path("container.tar")
    try:
        res = podman.run(["load", "-i", str(tarball_path)], capture_output=True)
        assert isinstance(res, str)
        # The stdout of the above command is usually 'Loaded image: sha256:<digest>'
        # we can get the image digest by grabbing the last part of stdout.
        return res.split()[-1]
    except subprocess.CalledProcessError as e:
        if e.stderr:
            error = e.stderr.decode()
        else:
            error = "No output"
        raise errors.ImageInstallationException(
            f"Could not install container image: {error}"
        )


def tag_image_by_digest(digest: str, tag: str) -> None:
    """Tag a container image by digest."""
    podman = init_podman_command()
    image = Image.from_digest(digest)
    podman.run(["tag", image.id, tag])


def get_image_id_by_digest(digest: str) -> str:
    """Get an image ID from a digest."""
    return Image.from_digest(digest).id


def expected_image_name() -> str:
    image_name_path = get_resource_path("image-name.txt")
    return image_name_path.read_text().strip("\n")


def container_pull(image: str, manifest_digest: str) -> None:
    """Pull a container image from a registry."""
    manifest_digest = normalize_digest(manifest_digest)
    podman = init_podman_command()
    try:
        podman.run(["pull", f"{image}@{manifest_digest}"], capture_output=False)
    except CommandError:
        raise errors.ContainerPullException("Could not pull the container image")


def list_image_digests() -> list[str]:
    images = Image.list_dangerzone_images()
    return list({digest for image in images for digest in image.digests})


def get_local_image_digests(image: str | None = None) -> str:
    """Return all known digests for a local image name."""
    return Image.get_dangerzone_image().digests
