import gzip
import json
import logging
import os
import pathlib
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable, List, Optional, Tuple

from ..conversion.errors import exception_from_error_code
from ..document import Document
from ..util import (
    get_resource_path,
    get_subprocess_startupinfo,
    get_tmp_dir,
    replace_control_chars,
)
from .base import (
    MAX_CONVERSION_LOG_CHARS,
    PIXELS_TO_PDF_LOG_END,
    PIXELS_TO_PDF_LOG_START,
    IsolationProvider,
)

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

    def __init__(self, enable_timeouts: bool) -> None:
        self.enable_timeouts = 1 if enable_timeouts else 0
        super().__init__()

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

    def assert_field_type(self, val: Any, _type: object) -> None:
        # XXX: Use a stricter check than isinstance because `bool` is a subclass of
        # `int`.
        #
        # See https://stackoverflow.com/a/37888668
        if not type(val) == _type:
            raise ValueError("Status field has incorrect type")

    def parse_progress(self, document: Document, untrusted_line: str) -> None:
        """
        Parses a line returned by the container.
        """
        try:
            untrusted_status = json.loads(untrusted_line)

            text = untrusted_status["text"]
            self.assert_field_type(text, str)

            error = untrusted_status["error"]
            self.assert_field_type(error, bool)

            percentage = untrusted_status["percentage"]
            self.assert_field_type(percentage, int)

            self.print_progress(document, error, text, percentage)
        except Exception:
            line = replace_control_chars(untrusted_line)
            error_message = (
                f"Invalid JSON returned from container:\n\n\tUNTRUSTED> {line}"
            )
            self.print_progress_trusted(document, True, error_message, -1)

    def exec(
        self,
        document: Document,
        args: List[str],
    ) -> int:
        args_str = " ".join(shlex.quote(s) for s in args)
        log.info("> " + args_str)

        with subprocess.Popen(
            args,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            startupinfo=startupinfo,
        ) as p:
            if p.stdout is not None:
                for untrusted_line in p.stdout:
                    self.parse_progress(document, untrusted_line)

            p.communicate()
            return p.returncode

    def exec_container(
        self,
        document: Document,
        command: List[str],
        extra_args: List[str] = [],
    ) -> int:
        container_runtime = self.get_runtime()

        if self.get_runtime_name() == "podman":
            security_args = ["--security-opt", "no-new-privileges"]
            security_args += ["--userns", "keep-id"]
        else:
            security_args = ["--security-opt=no-new-privileges:true"]

        # drop all linux kernel capabilities
        security_args += ["--cap-drop", "all"]
        user_args = ["-u", "dangerzone"]

        prevent_leakage_args = ["--rm"]

        args = (
            ["run", "--network", "none"]
            + user_args
            + security_args
            + prevent_leakage_args
            + extra_args
            + [self.CONTAINER_NAME]
            + command
        )

        args = [container_runtime] + args
        return self.exec(document, args)

    def _convert(
        self,
        document: Document,
        ocr_lang: Optional[str],
    ) -> bool:
        # Create a temporary directory inside the cache directory for this run. Then,
        # create some subdirectories for the various stages of the file conversion:
        #
        # * unsafe: Where the input file will be copied
        # * pixel: Where the RGB data will be stored
        # * safe: Where the final PDF file will be stored
        with tempfile.TemporaryDirectory(dir=get_tmp_dir()) as t:
            tmp_dir = pathlib.Path(t)
            unsafe_dir = tmp_dir / "unsafe"
            unsafe_dir.mkdir()
            pixel_dir = tmp_dir / "pixels"
            pixel_dir.mkdir()
            safe_dir = tmp_dir / "safe"
            safe_dir.mkdir()

            return self._convert_with_tmpdirs(
                document=document,
                unsafe_dir=unsafe_dir,
                pixel_dir=pixel_dir,
                safe_dir=safe_dir,
                ocr_lang=ocr_lang,
            )

    def _convert_with_tmpdirs(
        self,
        document: Document,
        unsafe_dir: pathlib.Path,
        pixel_dir: pathlib.Path,
        safe_dir: pathlib.Path,
        ocr_lang: Optional[str],
    ) -> bool:
        success = False

        if ocr_lang:
            ocr = "1"
        else:
            ocr = "0"

        copied_file = unsafe_dir / "input_file"
        shutil.copyfile(f"{document.input_filename}", copied_file)

        # Convert document to pixels
        command = [
            "/usr/bin/python3",
            "-m",
            "dangerzone.conversion.doc_to_pixels",
        ]
        extra_args = [
            "-v",
            f"{copied_file}:/tmp/input_file:Z",
            "-v",
            f"{pixel_dir}:/tmp/dangerzone:Z",
            "-e",
            f"ENABLE_TIMEOUTS={self.enable_timeouts}",
        ]
        ret = self.exec_container(document, command, extra_args)

        if getattr(sys, "dangerzone_dev", False):
            log_path = pixel_dir / "captured_output.txt"
            with open(log_path, "r", encoding="ascii", errors="replace") as f:
                untrusted_log = f.read(MAX_CONVERSION_LOG_CHARS)
            log.info(
                f"Conversion output (doc to pixels):\n{self.sanitize_conversion_str(untrusted_log)}"
            )

        if ret != 0:
            log.error("documents-to-pixels failed")

            # XXX Reconstruct exception from error code
            raise exception_from_error_code(ret)  # type: ignore [misc]
        else:
            # TODO: validate convert to pixels output

            # Convert pixels to safe PDF
            command = [
                "/usr/bin/python3",
                "-m",
                "dangerzone.conversion.pixels_to_pdf",
            ]
            extra_args = [
                "-v",
                f"{pixel_dir}:/tmp/dangerzone:Z",
                "-v",
                f"{safe_dir}:/safezone:Z",
                "-e",
                "TESSDATA_PREFIX=/usr/share/tessdata",
                "-e",
                f"OCR={ocr}",
                "-e",
                f"OCR_LANGUAGE={ocr_lang}",
                "-e",
                f"ENABLE_TIMEOUTS={self.enable_timeouts}",
            ]
            ret = self.exec_container(document, command, extra_args)
            if ret != 0:
                log.error("pixels-to-pdf failed")
            else:
                # Move the final file to the right place
                if os.path.exists(document.output_filename):
                    os.remove(document.output_filename)

                container_output_filename = os.path.join(
                    safe_dir, "safe-output-compressed.pdf"
                )
                shutil.move(container_output_filename, document.output_filename)

                # We did it
                success = True

        if getattr(sys, "dangerzone_dev", False):
            log_path = safe_dir / "captured_output.txt"
            if log_path.exists():  # If first stage failed this may not exist
                with open(log_path, "r", encoding="ascii", errors="replace") as f:
                    text = (
                        f"Container output: (pixels to PDF)\n"
                        f"{PIXELS_TO_PDF_LOG_START}\n{f.read()}{PIXELS_TO_PDF_LOG_END}"
                    )
                    log.info(text)

        return success

    def get_max_parallel_conversions(self) -> int:
        # FIXME hardcoded 1 until timeouts are more limited and better handled
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
