import contextlib
import logging
import os
import platform
import signal
import subprocess
import sys
import threading
from abc import ABC, abstractmethod
from io import BytesIO
from typing import IO, Callable, Iterator, Optional

import fitz
from colorama import Fore, Style

from ..conversion import errors
from ..conversion.common import DEFAULT_DPI, INT_BYTES
from ..document import Document
from ..util import get_tessdata_dir, replace_control_chars

log = logging.getLogger(__name__)

TIMEOUT_EXCEPTION = 15
TIMEOUT_GRACE = 15
TIMEOUT_FORCE = 5


def _signal_process_group(p: subprocess.Popen, signo: int) -> None:
    """Send a signal to a process group."""
    try:
        os.killpg(os.getpgid(p.pid), signo)
    except (ProcessLookupError, PermissionError):
        # If the process no longer exists, we may encounter the above errors, either
        # when looking for the process group (ProcessLookupError), or when trying to
        # kill a process group that no longer exists (PermissionError)
        return
    except Exception:
        log.exception(
            f"Unexpected error while sending signal {signo} to the"
            f"document-to-pixels process group (PID: {p.pid})"
        )


def terminate_process_group(p: subprocess.Popen) -> None:
    """Terminate a process group."""
    if platform.system() == "Windows":
        p.terminate()
    else:
        _signal_process_group(p, signal.SIGTERM)


def kill_process_group(p: subprocess.Popen) -> None:
    """Forcefully kill a process group."""
    if platform.system() == "Windows":
        p.kill()
    else:
        _signal_process_group(p, signal.SIGKILL)


def read_bytes(f: IO[bytes], size: int, exact: bool = True) -> bytes:
    """Read bytes from a file-like object."""
    buf = f.read(size)
    if exact and len(buf) != size:
        raise errors.ConverterProcException()
    return buf


def read_int(f: IO[bytes]) -> int:
    """Read 2 bytes from a file-like object, and decode them as int."""
    untrusted_int = f.read(INT_BYTES)
    if len(untrusted_int) != INT_BYTES:
        raise errors.ConverterProcException()
    return int.from_bytes(untrusted_int, "big", signed=False)


def sanitize_debug_text(text: bytes) -> str:
    """Read all the buffer and return a sanitized version"""
    untrusted_text = text.decode("ascii", errors="replace")
    return replace_control_chars(untrusted_text, keep_newlines=True)


class IsolationProvider(ABC):
    """
    Abstracts an isolation provider
    """

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        if self.should_capture_stderr():
            self.proc_stderr = subprocess.PIPE
        else:
            self.proc_stderr = subprocess.DEVNULL

    def should_capture_stderr(self) -> bool:
        return self.debug or getattr(sys, "dangerzone_dev", False)

    def convert(
        self,
        document: Document,
        ocr_lang: Optional[str],
        progress_callback: Optional[Callable] = None,
    ) -> None:
        self.progress_callback = progress_callback
        document.mark_as_converting()
        try:
            with self.doc_to_pixels_proc(document) as conversion_proc:
                self.convert_with_proc(document, ocr_lang, conversion_proc)
            document.mark_as_safe()
            if document.archive_after_conversion:
                document.archive()
        except errors.ConversionException as e:
            self.print_progress(document, True, str(e), 0)
            document.mark_as_failed()
        except Exception as e:
            log.exception(
                f"An exception occurred while converting document '{document.id}'"
            )
            self.print_progress(document, True, str(e), 0)
            document.mark_as_failed()

    def ocr_page(self, pixmap: fitz.Pixmap, ocr_lang: str) -> bytes:
        """Get a single page as pixels, OCR it, and return a PDF as bytes."""
        return pixmap.pdfocr_tobytes(
            compress=True,
            language=ocr_lang,
            tessdata=str(get_tessdata_dir()),
        )

    def pixels_to_pdf_page(
        self,
        untrusted_data: bytes,
        untrusted_width: int,
        untrusted_height: int,
        ocr_lang: Optional[str],
    ) -> fitz.Document:
        """Convert a byte array of RGB pixels into a PDF page, optionally with OCR."""
        pixmap = fitz.Pixmap(
            fitz.Colorspace(fitz.CS_RGB),
            untrusted_width,
            untrusted_height,
            untrusted_data,
            False,
        )
        pixmap.set_dpi(DEFAULT_DPI, DEFAULT_DPI)

        if ocr_lang:  # OCR the document
            page_pdf_bytes = self.ocr_page(pixmap, ocr_lang)
        else:  # Don't OCR
            page_doc = fitz.Document()
            page_doc.insert_file(pixmap)
            page_pdf_bytes = page_doc.tobytes(deflate_images=True)

        return fitz.open("pdf", page_pdf_bytes)

    def convert_with_proc(
        self,
        document: Document,
        ocr_lang: Optional[str],
        p: subprocess.Popen,
    ) -> None:
        percentage = 0.0
        with open(document.input_filename, "rb") as f:
            try:
                assert p.stdin is not None
                p.stdin.write(f.read())
                p.stdin.close()
            except BrokenPipeError:
                raise errors.ConverterProcException()

            assert p.stdout
            n_pages = read_int(p.stdout)
            if n_pages == 0 or n_pages > errors.MAX_PAGES:
                raise errors.MaxPagesException()
            step = 100 / n_pages

            safe_doc = fitz.Document()

            for page in range(1, n_pages + 1):
                searchable = "searchable " if ocr_lang else ""
                text = (
                    f"Converting page {page}/{n_pages} from pixels to {searchable}PDF"
                )
                self.print_progress(document, False, text, percentage)

                width = read_int(p.stdout)
                height = read_int(p.stdout)
                if not (1 <= width <= errors.MAX_PAGE_WIDTH):
                    raise errors.MaxPageWidthException()
                if not (1 <= height <= errors.MAX_PAGE_HEIGHT):
                    raise errors.MaxPageHeightException()

                num_pixels = width * height * 3  # three color channels
                untrusted_pixels = read_bytes(
                    p.stdout,
                    num_pixels,
                )

                page_pdf = self.pixels_to_pdf_page(
                    untrusted_pixels,
                    width,
                    height,
                    ocr_lang,
                )
                safe_doc.insert_pdf(page_pdf)

                percentage += step

        # Ensure nothing else is read after all bitmaps are obtained
        p.stdout.close()

        # Saving it with a different name first, because PyMuPDF cannot handle
        # non-Unicode chars.
        safe_doc.save(document.sanitized_output_filename)
        os.replace(document.sanitized_output_filename, document.output_filename)

        # TODO handle leftover code input
        text = "Successfully converted document"
        self.print_progress(document, False, text, 100)

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

    def get_proc_exception(
        self, p: subprocess.Popen, timeout: int = TIMEOUT_EXCEPTION
    ) -> Exception:
        """Returns an exception associated with a process exit code"""
        try:
            error_code = p.wait(timeout)
        except subprocess.TimeoutExpired:
            return errors.UnexpectedConversionError(
                "Encountered an I/O error during document to pixels conversion,"
                f" but the conversion process is still running after {timeout} seconds"
                f" (PID: {p.pid})"
            )
        except Exception:
            return errors.UnexpectedConversionError(
                "Encountered an I/O error during document to pixels conversion,"
                f" but the status of the conversion process is unknown (PID: {p.pid})"
            )
        return errors.exception_from_error_code(error_code)

    @abstractmethod
    def requires_install(self) -> bool:
        """Whether this isolation provider needs an installation step"""
        pass

    @abstractmethod
    def get_max_parallel_conversions(self) -> int:
        pass

    @abstractmethod
    def start_doc_to_pixels_proc(self, document: Document) -> subprocess.Popen:
        pass

    @abstractmethod
    def terminate_doc_to_pixels_proc(
        self, document: Document, p: subprocess.Popen
    ) -> None:
        """Terminate gracefully the process started for the doc-to-pixels phase."""
        pass

    def ensure_stop_doc_to_pixels_proc(
        self,
        document: Document,
        p: subprocess.Popen,
        timeout_grace: int = TIMEOUT_GRACE,
        timeout_force: int = TIMEOUT_FORCE,
    ) -> None:
        """Stop the conversion process, or ensure it has exited.

        This method should be called when we want to verify that the doc-to-pixels
        process has exited, or terminate it ourselves. The termination should happen as
        gracefully as possible, and we should not block indefinitely until the process
        has exited.
        """
        # Check if the process completed.
        ret = p.poll()
        if ret is not None:
            return

        # At this point, the process is still running. This may be benign, as we haven't
        # waited for it yet. Terminate it gracefully.
        self.terminate_doc_to_pixels_proc(document, p)
        try:
            p.wait(timeout_grace)
        except subprocess.TimeoutExpired:
            log.warning(
                f"Conversion process did not terminate gracefully after {timeout_grace}"
                " seconds. Killing it forcefully..."
            )

            # Forcefully kill the running process.
            kill_process_group(p)
            try:
                p.wait(timeout_force)
            except subprocess.TimeoutExpired:
                log.warning(
                    "Conversion process did not terminate forcefully after"
                    f" {timeout_force} seconds. Resources may linger..."
                )

    @contextlib.contextmanager
    def doc_to_pixels_proc(
        self,
        document: Document,
        timeout_exception: int = TIMEOUT_EXCEPTION,
        timeout_grace: int = TIMEOUT_GRACE,
        timeout_force: int = TIMEOUT_FORCE,
    ) -> Iterator[subprocess.Popen]:
        """Start a conversion process, pass it to the caller, and then clean it up."""
        # Store the proc stderr in memory
        stderr = BytesIO()
        p = self.start_doc_to_pixels_proc(document)
        stderr_thread = self.start_stderr_thread(p, stderr)

        if platform.system() != "Windows":
            assert os.getpgid(p.pid) != os.getpgid(os.getpid()), (
                "Parent shares same PGID with child"
            )

        try:
            yield p
        except errors.ConverterProcException as e:
            exception = self.get_proc_exception(p, timeout_exception)
            raise exception from e
        finally:
            self.ensure_stop_doc_to_pixels_proc(
                document, p, timeout_grace=timeout_grace, timeout_force=timeout_force
            )

            if stderr_thread:
                # Wait for the thread to complete. If it's still alive, mention it in the debug log.
                stderr_thread.join(timeout=1)

                debug_bytes = stderr.getvalue()
                debug_log = sanitize_debug_text(debug_bytes)

                incomplete = "(incomplete) " if stderr_thread.is_alive() else ""

                log.info(
                    "Conversion output (doc to pixels)\n"
                    f"----- DOC TO PIXELS LOG START {incomplete}-----\n"
                    f"{debug_log}"  # no need for an extra newline here
                    "----- DOC TO PIXELS LOG END -----"
                )

    def start_stderr_thread(
        self, process: subprocess.Popen, stderr: IO[bytes]
    ) -> Optional[threading.Thread]:
        """Start a thread to read stderr from the process"""

        def _stream_stderr(process_stderr: IO[bytes]) -> None:
            try:
                for line in process_stderr:
                    stderr.write(line)
            except (ValueError, IOError) as e:
                log.debug(f"Stderr stream closed: {e}")

        if process.stderr:
            stderr_thread = threading.Thread(
                target=_stream_stderr,
                args=(process.stderr,),
                daemon=True,
            )
            stderr_thread.start()
            return stderr_thread
        return None
