import logging
import os
import platform
import shlex
import subprocess
import sys
from typing import Callable, List, Optional, Tuple

from .. import container_utils, errors
from ..container_utils import make_seccomp_json_accessible, subprocess_run
from ..document import Document
from ..settings import Settings
from ..updater import (
    DEFAULT_PUBKEY_LOCATION,
    UpdaterError,
    bypass_signature_checks,
    upgrade_container_image,
    verify_local_image,
)
from ..util import (
    get_resource_path,
    get_subprocess_startupinfo,
)
from .base import IsolationProvider, terminate_process_group

TIMEOUT_KILL = 5  # Timeout in seconds until the kill command returns.
MINIMUM_DOCKER_DESKTOP = {
    "Darwin": "4.43.1",
    "Windows": "4.43.1",
}

# Define startupinfo for subprocesses
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()  # type: ignore [attr-defined]
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore [attr-defined]
else:
    startupinfo = None


log = logging.getLogger(__name__)


class Container(IsolationProvider):
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
        """
        security_args = ["--log-driver", "none"]
        security_args += ["--security-opt", "no-new-privileges"]
        if container_utils.get_runtime_version() >= (4, 1):
            security_args += ["--userns", "nomap"]

        # We specify a custom seccomp policy uniformly, because on certain container
        # engines the default policy might not allow the `ptrace(2)` syscall [1]. Our
        # custom seccomp policy has been copied as is [2] from the official Podman repo.
        #
        # [1] https://github.com/freedomofpress/dangerzone/issues/846
        # [2] https://github.com/containers/common/blob/d3283f8401eeeb21f3c59a425b5461f069e199a7/pkg/seccomp/seccomp.json
        seccomp_json_path = make_seccomp_json_accessible()
        security_args += ["--security-opt", f"seccomp={seccomp_json_path}"]

        security_args += ["--cap-drop", "all"]
        security_args += ["--cap-add", "SYS_CHROOT"]
        security_args += ["--security-opt", "label=type:container_engine_t"]

        security_args += ["--network=none"]
        security_args += ["-u", "dangerzone"]

        return security_args

    @staticmethod
    def requires_install() -> bool:
        return True

    def doc_to_pixels_container_name(self, document: Document) -> str:
        """Unique container name for the doc-to-pixels phase."""
        return f"dangerzone-doc-to-pixels-{document.id}"

    def pixels_to_pdf_container_name(self, document: Document) -> str:
        """Unique container name for the pixels-to-pdf phase."""
        return f"dangerzone-pixels-to-pdf-{document.id}"

    def exec_container(
        self,
        command: List[str],
        name: str,
    ) -> subprocess.Popen:
        container_name = container_utils.expected_image_name()
        image_digest = container_utils.get_local_image_digest()
        if not bypass_signature_checks():
            verify_local_image(image_digest=image_digest)
        security_args = self.get_runtime_security_args()
        debug_args = []
        if self.debug:
            debug_args += ["-e", "RUNSC_DEBUG=1"]

        enable_stdin = ["-i"]
        set_name = ["--name", name]
        prevent_leakage_args = ["--rm"]
        image_name = [container_name + "@sha256:" + image_digest]
        args = (
            ["run"]
            + security_args
            + debug_args
            + prevent_leakage_args
            + enable_stdin
            + set_name
            + image_name
            + command
        )
        podman = container_utils.init_podman_command()
        return podman.run(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.proc_stderr,
            # Start the conversion process in a new session, so that we can later on
            # kill the process group, without killing the controlling script.
            start_new_session=True,
            wait=False,
        )

    def kill_container(self, name: str) -> None:
        """Terminate a spawned container.

        We choose to terminate spawned containers using the `kill` action that the
        container runtime provides, instead of terminating the process that spawned
        them. The reason is that this process is not always tied to the underlying
        container. For instance, in Docker containers, this process is actually
        connected to the Docker daemon, and killing it will just close the associated
        standard streams.
        """
        podman = container_utils.init_podman_command()
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
        name = self.doc_to_pixels_container_name(document)
        return self.exec_container(command, name=name)

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
        podman = container_utils.init_podman_command()
        name = self.doc_to_pixels_container_name(document)
        all_containers = podman.run(["ps", "-a"])
        if name in all_containers:  # type:ignore[attr-defined]
            log.warning(f"Container '{name}' did not stop gracefully")

    def get_max_parallel_conversions(self) -> int:
        # FIXME hardcoded 1 until length conversions are better handled
        # https://github.com/freedomofpress/dangerzone/issues/257
        return 1

        n_cpu = 1
        if platform.system() == "Linux":
            # if on linux containers run natively
            cpu_count = os.cpu_count()
            if cpu_count is not None:
                n_cpu = cpu_count
        else:
            # For Windows and MacOS containers run in VM
            # So we obtain the CPU count for the VM
            n_cpu_str = subprocess.check_output(
                [str(runtime.path), "info", "--format", "{{.NCPU}}"],
                text=True,
                startupinfo=get_subprocess_startupinfo(),
            )
            n_cpu = int(n_cpu_str.strip())

        return 2 * n_cpu + 1
