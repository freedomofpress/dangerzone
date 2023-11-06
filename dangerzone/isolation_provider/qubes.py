import asyncio
import glob
import inspect
import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import IO, Callable, Optional

from ..conversion import errors
from ..conversion.common import calculate_timeout, running_on_qubes
from ..conversion.pixels_to_pdf import PixelsToPDF
from ..document import Document
from ..util import (
    Stopwatch,
    get_resource_path,
    get_subprocess_startupinfo,
    get_tmp_dir,
    nonblocking_read,
)
from .base import (
    MAX_CONVERSION_LOG_CHARS,
    PIXELS_TO_PDF_LOG_END,
    PIXELS_TO_PDF_LOG_START,
    IsolationProvider,
)

log = logging.getLogger(__name__)

# The maximum time a qube takes to start up.
STARTUP_TIME_SECONDS = 5 * 60  # 5 minutes


def read_bytes(f: IO[bytes], size: int, timeout: float, exact: bool = True) -> bytes:
    """Read bytes from a file-like object."""
    buf = nonblocking_read(f, size, timeout)
    if exact and len(buf) != size:
        raise errors.InterruptedConversion
    return buf


def read_int(f: IO[bytes], timeout: float) -> int:
    """Read 2 bytes from a file-like object, and decode them as int."""
    untrusted_int = read_bytes(f, 2, timeout)
    return int.from_bytes(untrusted_int, signed=False)


def read_debug_text(f: IO[bytes], size: int) -> str:
    """Read arbitrarily long text (for debug purposes)"""
    timeout = calculate_timeout(size)
    untrusted_text = read_bytes(f, size, timeout, exact=False)
    return untrusted_text.decode("ascii", errors="replace")


class Qubes(IsolationProvider):
    """Uses a disposable qube for performing the conversion"""

    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen] = None
        super().__init__()

    def install(self) -> bool:
        return True

    def _convert_with_tmpdirs(
        self,
        document: Document,
        tempdir: str,
        ocr_lang: Optional[str] = None,
    ) -> bool:
        success = False

        Path(f"{tempdir}/dangerzone").mkdir()
        percentage = 0.0

        with open(document.input_filename, "rb") as f:
            self.proc = self.qrexec_subprocess()
            try:
                assert self.proc.stdin is not None
                self.proc.stdin.write(f.read())
                self.proc.stdin.close()
            except BrokenPipeError as e:
                raise errors.InterruptedConversion()

            # Get file size (in MiB)
            size = os.path.getsize(document.input_filename) / 1024**2
            timeout = calculate_timeout(size) + STARTUP_TIME_SECONDS

            assert self.proc is not None
            assert self.proc.stdout is not None
            os.set_blocking(self.proc.stdout.fileno(), False)

            n_pages = read_int(self.proc.stdout, timeout)
            if n_pages == 0 or n_pages > errors.MAX_PAGES:
                raise errors.MaxPagesException()
            percentage_per_page = 50.0 / n_pages

            timeout = calculate_timeout(size, n_pages)
            sw = Stopwatch(timeout)
            sw.start()
            for page in range(1, n_pages + 1):
                text = f"Converting page {page}/{n_pages} to pixels"
                self.print_progress_trusted(document, False, text, percentage)

                width = read_int(self.proc.stdout, timeout=sw.remaining)
                height = read_int(self.proc.stdout, timeout=sw.remaining)
                if not (1 <= width <= errors.MAX_PAGE_WIDTH):
                    raise errors.MaxPageWidthException()
                if not (1 <= height <= errors.MAX_PAGE_HEIGHT):
                    raise errors.MaxPageHeightException()

                num_pixels = width * height * 3  # three color channels
                untrusted_pixels = read_bytes(
                    self.proc.stdout,
                    num_pixels,
                    timeout=sw.remaining,
                )

                # Wrapper code
                with open(f"{tempdir}/dangerzone/page-{page}.width", "w") as f_width:
                    f_width.write(str(width))
                with open(f"{tempdir}/dangerzone/page-{page}.height", "w") as f_height:
                    f_height.write(str(height))
                with open(f"{tempdir}/dangerzone/page-{page}.rgb", "wb") as f_rgb:
                    f_rgb.write(untrusted_pixels)

                percentage += percentage_per_page

        # Ensure nothing else is read after all bitmaps are obtained
        self.proc.stdout.close()

        # TODO handle leftover code input
        text = "Converted document to pixels"
        self.print_progress_trusted(document, False, text, percentage)

        if getattr(sys, "dangerzone_dev", False):
            assert self.proc.stderr is not None
            os.set_blocking(self.proc.stderr.fileno(), False)
            untrusted_log = read_debug_text(self.proc.stderr, MAX_CONVERSION_LOG_CHARS)
            self.proc.stderr.close()
            log.info(
                f"Conversion output (doc to pixels)\n{self.sanitize_conversion_str(untrusted_log)}"
            )

        def print_progress_wrapper(error: bool, text: str, percentage: float) -> None:
            self.print_progress_trusted(document, error, text, percentage)

        converter = PixelsToPDF(progress_callback=print_progress_wrapper)
        try:
            asyncio.run(converter.convert(ocr_lang, tempdir))
        except (RuntimeError, TimeoutError, ValueError) as e:
            raise errors.UnexpectedConversionError(str(e))
        finally:
            if getattr(sys, "dangerzone_dev", False):
                out = converter.captured_output.decode()
                text = (
                    f"Conversion output: (pixels to PDF)\n"
                    f"{PIXELS_TO_PDF_LOG_START}\n{out}{PIXELS_TO_PDF_LOG_END}"
                )
                log.info(text)

        shutil.move(f"{tempdir}/safe-output-compressed.pdf", document.output_filename)
        success = True

        return success

    def _convert(
        self,
        document: Document,
        ocr_lang: Optional[str] = None,
    ) -> bool:
        try:
            with tempfile.TemporaryDirectory() as t:
                return self._convert_with_tmpdirs(document, t, ocr_lang)
        except errors.InterruptedConversion:
            assert self.proc is not None
            error_code = self.proc.wait(3)
            # XXX Reconstruct exception from error code
            raise errors.exception_from_error_code(error_code)  # type: ignore [misc]

    def get_max_parallel_conversions(self) -> int:
        return 1

    def qrexec_subprocess(self) -> subprocess.Popen:
        dev_mode = getattr(sys, "dangerzone_dev", False) == True
        if dev_mode:
            # Use dz.ConvertDev RPC call instead, if we are in development mode.
            # Basically, the change is that we also transfer the necessary Python
            # code as a zipfile, before sending the doc that the user requested.
            qrexec_policy = "dz.ConvertDev"
            stderr = subprocess.PIPE
        else:
            qrexec_policy = "dz.Convert"
            stderr = subprocess.DEVNULL

        p = subprocess.Popen(
            ["/usr/bin/qrexec-client-vm", "@dispvm:dz-dvm", qrexec_policy],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
        )

        if dev_mode:
            assert p.stdin is not None
            # Send the dangerzone module first.
            self.teleport_dz_module(p.stdin)

        return p

    def teleport_dz_module(self, wpipe: IO[bytes]) -> None:
        """Send the dangerzone module to another qube, as a zipfile."""
        # Grab the absolute file path of the dangerzone module.
        import dangerzone.conversion as _conv

        _conv_path = Path(inspect.getfile(_conv)).parent
        temp_file = io.BytesIO()

        # Create a Python zipfile that contains all the files of the dangerzone module.
        with zipfile.PyZipFile(temp_file, "w") as z:
            z.mkdir("dangerzone/")
            z.writestr("dangerzone/__init__.py", "")
            z.writepy(str(_conv_path), basename="dangerzone/")

        # Send the following data:
        # 1. The size of the Python zipfile, so that the server can know when to
        #    stop.
        # 2. The Python zipfile itself.
        bufsize_bytes = len(temp_file.getvalue()).to_bytes(4)
        wpipe.write(bufsize_bytes)
        wpipe.write(temp_file.getvalue())


def is_qubes_native_conversion() -> bool:
    """Returns True if the conversion should be run using Qubes OS's diposable
    VMs and False if not."""
    if running_on_qubes():
        if getattr(sys, "dangerzone_dev", False):
            return os.environ.get("QUBES_CONVERSION", "0") == "1"

        # XXX If Dangerzone is installed check if container image was shipped
        # This disambiguates if it is running a Qubes targetted build or not
        # (Qubes-specific builds don't ship the container image)

        compressed_container_path = get_resource_path("container.tar.gz")
        return not os.path.exists(compressed_container_path)
    else:
        return False
