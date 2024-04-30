import gzip
import json
import logging
import os
import platform
import shlex
import shutil
import subprocess
import sys
from typing import Any, List, Optional

from ..conversion import errors
from ..document import Document
from ..util import get_resource_path, get_subprocess_startupinfo, get_tmp_dir
from .base import PIXELS_TO_PDF_LOG_END, PIXELS_TO_PDF_LOG_START, IsolationProvider

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
    def get_runtime() -> str:
        container_tech = Container.get_runtime_name()
        runtime = shutil.which(container_tech)
        if runtime is None:
            raise NoContainerTechException(container_tech)
        return runtime

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

        chunk_size = 10240
        compressed_container_path = get_resource_path("container.tar.gz")
        with gzip.open(compressed_container_path) as f:
            while True:
                chunk = f.read(chunk_size)
                if len(chunk) > 0:
                    if p.stdin:
                        p.stdin.write(chunk)
                else:
                    break
        p.communicate()

        if not Container.is_container_installed():
            log.error("Failed to install the container image")
            return False

        log.info("Container image installed")
        return True

    @staticmethod
    def is_container_installed() -> bool:
        """
        See if the podman container is installed. Linux only.
        """
        # Get the image id
        with open(get_resource_path("image-id.txt")) as f:
            expected_image_id = f.read().strip()

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

        if found_image_id == expected_image_id:
            installed = True
        elif found_image_id == "":
            pass
        else:
            log.info("Deleting old dangerzone container image")

            try:
                subprocess.check_output(
                    [Container.get_runtime(), "rmi", "--force", found_image_id],
                    startupinfo=get_subprocess_startupinfo(),
                )
            except:
                log.warning("Couldn't delete old container image, so leaving it there")

        return installed

    def doc_to_pixels_container_name(self, document: Document) -> str:
        """Unique container name for the doc-to-pixels phase."""
        return f"dangerzone-doc-to-pixels-{document.id}"

    def pixels_to_pdf_container_name(self, document: Document) -> str:
        """Unique container name for the pixels-to-pdf phase."""
        return f"dangerzone-pixels-to-pdf-{document.id}"

    def assert_field_type(self, val: Any, _type: object) -> None:
        # XXX: Use a stricter check than isinstance because `bool` is a subclass of
        # `int`.
        #
        # See https://stackoverflow.com/a/37888668
        if not type(val) == _type:
            raise ValueError("Status field has incorrect type")

    def parse_progress_trusted(self, document: Document, line: str) -> None:
        """
        Parses a line returned by the container.
        """
        try:
            status = json.loads(line)
            text = status["text"]
            self.assert_field_type(text, str)
            error = status["error"]
            self.assert_field_type(error, bool)
            percentage = status["percentage"]
            self.assert_field_type(percentage, float)
            self.print_progress(document, error, text, percentage)
        except Exception:
            error_message = f"Invalid JSON returned from container:\n\n\t {line}"
            self.print_progress(document, True, error_message, -1)

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
        )

    def exec_container(
        self,
        command: List[str],
        name: str,
        extra_args: List[str] = [],
    ) -> subprocess.Popen:
        container_runtime = self.get_runtime()

        if self.get_runtime_name() == "podman":
            security_args = ["--log-driver", "none"]
            security_args += ["--security-opt", "no-new-privileges"]
            security_args += ["--userns", "keep-id"]
        else:
            security_args = ["--security-opt=no-new-privileges:true"]

        # drop all linux kernel capabilities
        security_args += ["--cap-drop", "all"]
        user_args = ["-u", "dangerzone"]
        enable_stdin = ["-i"]
        set_name = ["--name", name]

        prevent_leakage_args = ["--rm"]

        args = (
            ["run", "--network", "none"]
            + user_args
            + security_args
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
            subprocess.run(
                cmd, capture_output=True, startupinfo=get_subprocess_startupinfo()
            )
        except Exception as e:
            log.exception(
                f"Unexpected error occurred while killing container '{name}': {str(e)}"
            )

    def pixels_to_pdf(
        self, document: Document, tempdir: str, ocr_lang: Optional[str]
    ) -> None:
        # Convert pixels to safe PDF
        command = [
            "/usr/bin/python3",
            "-m",
            "dangerzone.conversion.pixels_to_pdf",
        ]
        extra_args = [
            "-v",
            f"{tempdir}:/safezone:Z",
            "-e",
            f"OCR={0 if ocr_lang is None else 1}",
            "-e",
            f"OCR_LANGUAGE={ocr_lang}",
        ]

        name = self.pixels_to_pdf_container_name(document)
        pixels_to_pdf_proc = self.exec_container(command, name, extra_args)
        if pixels_to_pdf_proc.stdout:
            for line in pixels_to_pdf_proc.stdout:
                self.parse_progress_trusted(document, line.decode())
        error_code = pixels_to_pdf_proc.wait()

        # In case of a dev run, log everything from the second container.
        if getattr(sys, "dangerzone_dev", False):
            assert pixels_to_pdf_proc.stderr
            out = pixels_to_pdf_proc.stderr.read().decode()
            text = (
                f"Conversion output: (pixels to PDF)\n"
                f"{PIXELS_TO_PDF_LOG_START}\n{out}\n{PIXELS_TO_PDF_LOG_END}"
            )
            log.info(text)

        if error_code != 0:
            log.error("pixels-to-pdf failed")
            raise errors.exception_from_error_code(error_code)
        else:
            # Move the final file to the right place
            if os.path.exists(document.output_filename):
                os.remove(document.output_filename)

            container_output_filename = os.path.join(
                tempdir, "safe-output-compressed.pdf"
            )
            shutil.move(container_output_filename, document.output_filename)

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
        p.terminate()

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
