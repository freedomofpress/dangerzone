import gzip
import logging
import os
import platform
import shlex
import shutil
import subprocess
from typing import List, Tuple

from ..document import Document
from ..util import get_resource_path, get_subprocess_startupinfo
from .base import IsolationProvider, terminate_process_group

TIMEOUT_KILL = 5  # Timeout in seconds until the kill command returns.


# Define startupinfo for subprocesses
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()  # type: ignore [attr-defined]
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore [attr-defined]
else:
    startupinfo = None


log = logging.getLogger(__name__)


class NoContainerTechException(Exception):
    def __init__(self, container_tech: str) -> None:
        super().__init__(f"{container_tech} is not installed")


class NotAvailableContainerTechException(Exception):
    def __init__(self, container_tech: str, error: str) -> None:
        self.error = error
        self.container_tech = container_tech
        super().__init__(f"{container_tech} is not available")


class ImageNotPresentException(Exception):
    pass


class ImageInstallationException(Exception):
    pass


class Container(IsolationProvider):
    # Name of the dangerzone container
    CONTAINER_NAME = "dangerzone.rocks/dangerzone"

    @staticmethod
    def get_runtime_name() -> str:
        if platform.system() == "Linux":
            runtime_name = "podman"
        else:
            # Windows, Darwin, and unknown use docker for now, dangerzone-vm eventually
            runtime_name = "docker"
        return runtime_name

    @staticmethod
    def get_runtime_version() -> Tuple[int, int]:
        """Get the major/minor parts of the Docker/Podman version.

        Some of the operations we perform in this module rely on some Podman features
        that are not available across all of our platforms. In order to have a proper
        fallback, we need to know the Podman version. More specifically, we're fine with
        just knowing the major and minor version, since writing/installing a full-blown
        semver parser is an overkill.
        """
        # Get the Docker/Podman version, using a Go template.
        runtime = Container.get_runtime_name()
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

    @staticmethod
    def get_runtime() -> str:
        container_tech = Container.get_runtime_name()
        runtime = shutil.which(container_tech)
        if runtime is None:
            raise NoContainerTechException(container_tech)
        return runtime

    @staticmethod
    def get_runtime_security_args() -> List[str]:
        """Security options applicable to the outer Dangerzone container.

        Our security precautions for the outer Dangerzone container are the following:
        * Do not let the container assume new privileges.
        * Drop all capabilities, except for CAP_SYS_CHROOT, which is necessary for
          running gVisor.
        * Do not allow access to the network stack.
        * Run the container as the unprivileged `dangerzone` user.
        * Set the `container_engine_t` SELinux label, which allows gVisor to work on
          SELinux-enforcing systems
          (see https://github.com/freedomofpress/dangerzone/issues/880).
        * Set a custom seccomp policy for every container engine, since the `ptrace(2)`
          system call is forbidden by some.

        For Podman specifically, where applicable, we also add the following:
        * Do not log the container's output.
        * Do not map the host user to the container, with `--userns nomap` (available
          from Podman 4.1 onwards)
          - This particular argument is specified in `start_doc_to_pixels_proc()`, but
            should move here once #748 is merged.
        """
        if Container.get_runtime_name() == "podman":
            security_args = ["--log-driver", "none"]
            security_args += ["--security-opt", "no-new-privileges"]
        else:
            security_args = ["--security-opt=no-new-privileges:true"]

        # We specify a custom seccomp policy uniformly, because on certain container
        # engines the default policy might not allow the `ptrace(2)` syscall [1]. Our
        # custom seccomp policy has been copied as is [2] from the official Podman repo.
        #
        # [1] https://github.com/freedomofpress/dangerzone/issues/846
        # [2] https://github.com/containers/common/blob/d3283f8401eeeb21f3c59a425b5461f069e199a7/pkg/seccomp/seccomp.json
        seccomp_json_path = get_resource_path("seccomp.gvisor.json")
        security_args += ["--security-opt", f"seccomp={seccomp_json_path}"]

        security_args += ["--cap-drop", "all"]
        security_args += ["--cap-add", "SYS_CHROOT"]
        security_args += ["--security-opt", "label=type:container_engine_t"]

        security_args += ["--network=none"]
        security_args += ["-u", "dangerzone"]

        return security_args

    @staticmethod
    def install() -> bool:
        """
        Make sure the podman container is installed. Linux only.
        """
        if Container.is_container_installed():
            return True

        # Load the container into podman
        log.info("Installing Dangerzone container image...")

        p = subprocess.Popen(
            [Container.get_runtime(), "load"],
            stdin=subprocess.PIPE,
            startupinfo=get_subprocess_startupinfo(),
        )

        chunk_size = 4 << 20
        compressed_container_path = get_resource_path("container.tar.gz")
        with gzip.open(compressed_container_path) as f:
            while True:
                chunk = f.read(chunk_size)
                if len(chunk) > 0:
                    if p.stdin:
                        p.stdin.write(chunk)
                else:
                    break
        _, err = p.communicate()
        if p.returncode < 0:
            if err:
                error = err.decode()
            else:
                error = "No output"
            raise ImageInstallationException(
                f"Could not install container image: {error}"
            )

        if not Container.is_container_installed(raise_on_error=True):
            return False

        log.info("Container image installed")
        return True

    @staticmethod
    def is_runtime_available() -> bool:
        container_runtime = Container.get_runtime()
        runtime_name = Container.get_runtime_name()
        # Can we run `docker/podman image ls` without an error
        with subprocess.Popen(
            [container_runtime, "image", "ls"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            startupinfo=get_subprocess_startupinfo(),
        ) as p:
            _, stderr = p.communicate()
            if p.returncode != 0:
                raise NotAvailableContainerTechException(runtime_name, stderr.decode())
            return True

    @staticmethod
    def is_container_installed(raise_on_error: bool = False) -> bool:
        """
        See if the container is installed.
        """
        # Get the image id
        with open(get_resource_path("image-id.txt")) as f:
            expected_image_ids = f.read().strip().split()

        # See if this image is already installed
        installed = False
        found_image_id = subprocess.check_output(
            [
                Container.get_runtime(),
                "image",
                "list",
                "--format",
                "{{.ID}}",
                Container.CONTAINER_NAME,
            ],
            text=True,
            startupinfo=get_subprocess_startupinfo(),
        )
        found_image_id = found_image_id.strip()

        if found_image_id in expected_image_ids:
            installed = True
        elif found_image_id == "":
            if raise_on_error:
                raise ImageNotPresentException(
                    "Image is not listed after installation. Bailing out."
                )
        else:
            msg = (
                f"{Container.CONTAINER_NAME} images found, but IDs do not match."
                f" Found: {found_image_id}, Expected: {','.join(expected_image_ids)}"
            )
            if raise_on_error:
                raise ImageNotPresentException(msg)
            log.info(msg)
            log.info("Deleting old dangerzone container image")

            try:
                subprocess.check_output(
                    [Container.get_runtime(), "rmi", "--force", found_image_id],
                    startupinfo=get_subprocess_startupinfo(),
                )
            except Exception:
                log.warning("Couldn't delete old container image, so leaving it there")

        return installed

    def doc_to_pixels_container_name(self, document: Document) -> str:
        """Unique container name for the doc-to-pixels phase."""
        return f"dangerzone-doc-to-pixels-{document.id}"

    def pixels_to_pdf_container_name(self, document: Document) -> str:
        """Unique container name for the pixels-to-pdf phase."""
        return f"dangerzone-pixels-to-pdf-{document.id}"

    def exec(
        self,
        args: List[str],
    ) -> subprocess.Popen:
        args_str = " ".join(shlex.quote(s) for s in args)
        log.info("> " + args_str)

        return subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.proc_stderr,
            startupinfo=startupinfo,
            # Start the conversion process in a new session, so that we can later on
            # kill the process group, without killing the controlling script.
            start_new_session=True,
        )

    def exec_container(
        self,
        command: List[str],
        name: str,
        extra_args: List[str] = [],
    ) -> subprocess.Popen:
        container_runtime = self.get_runtime()
        security_args = self.get_runtime_security_args()
        debug_args = []
        if self.debug:
            debug_args += ["-e", "RUNSC_DEBUG=1"]

        enable_stdin = ["-i"]
        set_name = ["--name", name]
        prevent_leakage_args = ["--rm"]
        args = (
            ["run"]
            + security_args
            + debug_args
            + prevent_leakage_args
            + enable_stdin
            + set_name
            + extra_args
            + [self.CONTAINER_NAME]
            + command
        )
        args = [container_runtime] + args
        return self.exec(args)

    def kill_container(self, name: str) -> None:
        """Terminate a spawned container.

        We choose to terminate spawned containers using the `kill` action that the
        container runtime provides, instead of terminating the process that spawned
        them. The reason is that this process is not always tied to the underlying
        container. For instance, in Docker containers, this process is actually
        connected to the Docker daemon, and killing it will just close the associated
        standard streams.
        """
        container_runtime = self.get_runtime()
        cmd = [container_runtime, "kill", name]
        try:
            # We do not check the exit code of the process here, since the container may
            # have stopped right before invoking this command. In that case, the
            # command's output will contain some error messages, so we capture them in
            # order to silence them.
            #
            # NOTE: We specify a timeout for this command, since we've seen it hang
            # indefinitely for specific files. See:
            # https://github.com/freedomofpress/dangerzone/issues/854
            subprocess.run(
                cmd,
                capture_output=True,
                startupinfo=get_subprocess_startupinfo(),
                timeout=TIMEOUT_KILL,
            )
        except subprocess.TimeoutExpired:
            log.warning(
                f"Could not kill container '{name}' within {TIMEOUT_KILL} seconds"
            )
        except Exception as e:
            log.exception(
                f"Unexpected error occurred while killing container '{name}': {str(e)}"
            )

    def start_doc_to_pixels_proc(self, document: Document) -> subprocess.Popen:
        # Convert document to pixels
        command = [
            "/usr/bin/python3",
            "-m",
            "dangerzone.conversion.doc_to_pixels",
        ]
        # NOTE: Using `--userns nomap` is available only on Podman >= 4.1.0.
        # XXX: Move this under `get_runtime_security_args()` once #748 is merged.
        extra_args = []
        if Container.get_runtime_name() == "podman":
            if Container.get_runtime_version() >= (4, 1):
                extra_args += ["--userns", "nomap"]

        name = self.doc_to_pixels_container_name(document)
        return self.exec_container(command, name=name, extra_args=extra_args)

    def terminate_doc_to_pixels_proc(
        self, document: Document, p: subprocess.Popen
    ) -> None:
        # There are two steps to gracefully terminate a conversion process:
        # 1. Kill the container, and check that it has exited.
        # 2. Gracefully terminate the conversion process, in case it's stuck on I/O
        #
        # See also https://github.com/freedomofpress/dangerzone/issues/791
        self.kill_container(self.doc_to_pixels_container_name(document))
        terminate_process_group(p)

    def ensure_stop_doc_to_pixels_proc(  # type: ignore [no-untyped-def]
        self, document: Document, *args, **kwargs
    ) -> None:
        super().ensure_stop_doc_to_pixels_proc(document, *args, **kwargs)

        # Check if the container no longer exists, either because we successfully killed
        # it, or because it exited on its own. We operate under the assumption that
        # after a podman kill / docker kill invocation, this will likely be the case,
        # else the container runtime (Docker/Podman) has experienced a problem, and we
        # should report it.
        container_runtime = self.get_runtime()
        name = self.doc_to_pixels_container_name(document)
        all_containers = subprocess.run(
            [container_runtime, "ps", "-a"],
            capture_output=True,
            startupinfo=get_subprocess_startupinfo(),
        )
        if name in all_containers.stdout.decode():
            log.warning(f"Container '{name}' did not stop gracefully")

    def get_max_parallel_conversions(self) -> int:
        # FIXME hardcoded 1 until length conversions are better handled
        # https://github.com/freedomofpress/dangerzone/issues/257
        return 1

        n_cpu = 1  # type: ignore [unreachable]
        if platform.system() == "Linux":
            # if on linux containers run natively
            cpu_count = os.cpu_count()
            if cpu_count is not None:
                n_cpu = cpu_count

        elif self.get_runtime_name() == "docker":
            # For Windows and MacOS containers run in VM
            # So we obtain the CPU count for the VM
            n_cpu_str = subprocess.check_output(
                [self.get_runtime(), "info", "--format", "{{.NCPU}}"],
                text=True,
                startupinfo=get_subprocess_startupinfo(),
            )
            n_cpu = int(n_cpu_str.strip())

        return 2 * n_cpu + 1
