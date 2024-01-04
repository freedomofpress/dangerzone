import logging
import os
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO, Callable, Optional

from colorama import Fore, Style

from ..conversion import errors
from ..conversion.common import calculate_timeout
from ..document import Document
from ..util import Stopwatch, nonblocking_read, replace_control_chars

log = logging.getLogger(__name__)

MAX_CONVERSION_LOG_CHARS = 150 * 50  # up to ~150 lines of 50 characters
DOC_TO_PIXELS_LOG_START = "----- DOC TO PIXELS LOG START -----"
DOC_TO_PIXELS_LOG_END = "----- DOC TO PIXELS LOG END -----"
PIXELS_TO_PDF_LOG_START = "----- PIXELS TO PDF LOG START -----"
PIXELS_TO_PDF_LOG_END = "----- PIXELS TO PDF LOG END -----"


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


class IsolationProvider(ABC):
    """
    Abstracts an isolation provider
    """

    STARTUP_TIME_SECONDS = 0  # The maximum time it takes a the provider to start up.

    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen] = None

        if getattr(sys, "dangerzone_dev", False) == True:
            self.proc_stderr = subprocess.PIPE
        else:
            self.proc_stderr = subprocess.DEVNULL

    @abstractmethod
    def install(self) -> bool:
        pass

    def convert(
        self,
        document: Document,
        ocr_lang: Optional[str],
        progress_callback: Optional[Callable] = None,
    ) -> None:
        self.progress_callback = progress_callback
        document.mark_as_converting()
        try:
            with tempfile.TemporaryDirectory() as t:
                Path(f"{t}/pixels").mkdir()
                self.doc_to_pixels(document, t)
                # TODO: validate convert to pixels output
                self.pixels_to_pdf(document, t, ocr_lang)
            document.mark_as_safe()
            if document.archive_after_conversion:
                document.archive()
        except errors.InterruptedConversion:
            assert self.proc is not None
            error_code = self.proc.wait(3)
            # XXX Reconstruct exception from error code
            exception = errors.exception_from_error_code(error_code)
            document.mark_as_failed()
        except errors.ConversionException as e:
            self.print_progress(document, True, str(e), 0)
            document.mark_as_failed()
        except Exception as e:
            log.exception(
                f"An exception occurred while converting document '{document.id}'"
            )
            self.print_progress(document, True, str(e), 0)
            document.mark_as_failed()

    def doc_to_pixels(self, document: Document, tempdir: str) -> None:
        percentage = 0.0
        with open(document.input_filename, "rb") as f:
            self.proc = self.start_doc_to_pixels_proc()
            try:
                assert self.proc.stdin is not None
                self.proc.stdin.write(f.read())
                self.proc.stdin.close()
            except BrokenPipeError as e:
                raise errors.InterruptedConversion()

            # Get file size (in MiB)
            size = os.path.getsize(document.input_filename) / 1024**2
            timeout = calculate_timeout(size) + self.STARTUP_TIME_SECONDS

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
                self.print_progress(document, False, text, percentage)

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
                with open(f"{tempdir}/pixels/page-{page}.width", "w") as f_width:
                    f_width.write(str(width))
                with open(f"{tempdir}/pixels/page-{page}.height", "w") as f_height:
                    f_height.write(str(height))
                with open(f"{tempdir}/pixels/page-{page}.rgb", "wb") as f_rgb:
                    f_rgb.write(untrusted_pixels)

                percentage += percentage_per_page

        # Ensure nothing else is read after all bitmaps are obtained
        self.proc.stdout.close()

        # TODO handle leftover code input
        text = "Converted document to pixels"
        self.print_progress(document, False, text, percentage)

        if getattr(sys, "dangerzone_dev", False):
            assert self.proc.stderr is not None
            os.set_blocking(self.proc.stderr.fileno(), False)
            untrusted_log = read_debug_text(self.proc.stderr, MAX_CONVERSION_LOG_CHARS)
            self.proc.stderr.close()
            log.info(
                f"Conversion output (doc to pixels)\n{self.sanitize_conversion_str(untrusted_log)}"
            )

    @abstractmethod
    def pixels_to_pdf(
        self, document: Document, tempdir: str, ocr_lang: Optional[str]
    ) -> None:
        pass

    def print_progress(
        self, document: Document, error: bool, text: str, percentage: float
    ) -> None:
        s = Style.BRIGHT + Fore.YELLOW + f"[doc {document.id}] "
        s += Fore.CYAN + f"{int(percentage)}% " + Style.RESET_ALL
        if error:
            s += Fore.RED + text + Style.RESET_ALL
            log.error(s)
        else:
            s += text
            log.info(s)

        if self.progress_callback:
            self.progress_callback(error, text, percentage)

    @abstractmethod
    def get_max_parallel_conversions(self) -> int:
        pass

    def sanitize_conversion_str(self, untrusted_conversion_str: str) -> str:
        conversion_string = replace_control_chars(untrusted_conversion_str)

        # Add armor (gpg-style)
        armor_start = f"{DOC_TO_PIXELS_LOG_START}\n"
        armor_end = DOC_TO_PIXELS_LOG_END
        return armor_start + conversion_string + armor_end

    @abstractmethod
    def start_doc_to_pixels_proc(self) -> subprocess.Popen:
        pass


# From global_common:

# def validate_convert_to_pixel_output(self, common, output):
#     """
#     Take the output from the convert to pixels tasks and validate it. Returns
#     a tuple like: (success (boolean), error_message (str))
#     """
#     max_image_width = 10000
#     max_image_height = 10000

#     # Did we hit an error?
#     for line in output.split("\n"):
#         if (
#             "failed:" in line
#             or "The document format is not supported" in line
#             or "Error" in line
#         ):
#             return False, output

#     # How many pages was that?
#     num_pages = None
#     for line in output.split("\n"):
#         if line.startswith("Document has "):
#             num_pages = line.split(" ")[2]
#             break
#     if not num_pages or not num_pages.isdigit() or int(num_pages) <= 0:
#         return False, "Invalid number of pages returned"
#     num_pages = int(num_pages)

#     # Make sure we have the files we expect
#     expected_filenames = []
#     for i in range(1, num_pages + 1):
#         expected_filenames += [
#             f"page-{i}.rgb",
#             f"page-{i}.width",
#             f"page-{i}.height",
#         ]
#     expected_filenames.sort()
#     actual_filenames = os.listdir(common.pixel_dir.name)
#     actual_filenames.sort()

#     if expected_filenames != actual_filenames:
#         return (
#             False,
#             f"We expected these files:\n{expected_filenames}\n\nBut we got these files:\n{actual_filenames}",
#         )

#     # Make sure the files are the correct sizes
#     for i in range(1, num_pages + 1):
#         with open(f"{common.pixel_dir.name}/page-{i}.width") as f:
#             w_str = f.read().strip()
#         with open(f"{common.pixel_dir.name}/page-{i}.height") as f:
#             h_str = f.read().strip()
#         w = int(w_str)
#         h = int(h_str)
#         if (
#             not w_str.isdigit()
#             or not h_str.isdigit()
#             or w <= 0
#             or w > max_image_width
#             or h <= 0
#             or h > max_image_height
#         ):
#             return False, f"Page {i} has invalid geometry"

#         # Make sure the RGB file is the correct size
#         if os.path.getsize(f"{common.pixel_dir.name}/page-{i}.rgb") != w * h * 3:
#             return False, f"Page {i} has an invalid RGB file size"

#     return True, True
