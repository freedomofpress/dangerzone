import contextlib
import itertools
import logging
import multiprocessing as mp
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
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


def _ocr_pool_initializer() -> None:
    """Initialize OCR worker processes with optimal thread settings."""
    # Limit Tesseract to 1 thread per worker
    os.environ["OMP_THREAD_LIMIT"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["IS_WORKER_PROCESS"] = "1"


def worker_ocr(ctx) -> bytes:
    """Worker function for multiprocessing OCR. Returns PDF bytes."""
    page = ctx["page"]
    width = ctx["width"]
    height = ctx["height"]
    num_pixels = ctx["num_pixels"]
    untrusted_pixels = ctx["untrusted_pixels"]
    tessdata_dir = ctx["tessdata_dir"]
    ocr_lang = ctx["ocr_lang"]

    start = time.perf_counter()

    try:
        pixmap = fitz.Pixmap(
            fitz.Colorspace(fitz.CS_RGB),
            width,
            height,
            untrusted_pixels,
            False,
        )
        pixmap.set_dpi(DEFAULT_DPI, DEFAULT_DPI)
        page_bytes = pixmap.pdfocr_tobytes(
            compress=True,
            language=ocr_lang,
            tessdata=tessdata_dir,
        )

        end = time.perf_counter()
        elapsed = end - start
        print(f"PAGE {page} finished in: {elapsed:.4f}")

        return (elapsed, page_bytes)
    except Exception as e:
        # Re-raise with a picklable exception to avoid multiprocessing errors
        # when the original exception contains unpicklable SWIG objects
        raise RuntimeError(str(e)) from None


def worker_deflate(ctx):
    page = ctx["page"]
    untrusted_width = ctx["width"]
    untrusted_height = ctx["height"]
    num_pixels = ctx["num_pixels"]
    untrusted_pixels = ctx["untrusted_pixels"]
    import time

    start = time.perf_counter()

    pixmap = fitz.Pixmap(
        fitz.Colorspace(fitz.CS_RGB),
        untrusted_width,
        untrusted_height,
        untrusted_pixels,
        False,
    )
    try:
        pixmap.set_dpi(DEFAULT_DPI, DEFAULT_DPI)
        page_doc = fitz.Document()
        page_doc.insert_file(pixmap)
        page_bytes = page_doc.tobytes(deflate_images=True)

        end = time.perf_counter()
        elapsed = end - start
        print(f"PAGE {page} finished in: {elapsed:.4f}")

        return (elapsed, page_bytes)
    except Exception as e:
        # Re-raise with a picklable exception to avoid multiprocessing errors
        # when the original exception contains unpicklable SWIG objects
        raise RuntimeError(str(e)) from None


def bounded_map(executor, func, iterable, depth: int):
    """
    Map a function over an iterable with a fixed queue depth.

    1. Submits jobs immediately starting from the first item.
    2. Limits active/pending jobs to 'depth'.
    3. Yields results in the original order.
    """
    it = iter(iterable)

    # Step 1: Submit the first 'N' jobs to fill the buffer
    futures = deque(executor.submit(func, item) for item in itertools.islice(it, depth))

    # Step 2: As each job finishes, yield it and submit a new one
    for item in it:
        yield futures.popleft().result()  # Blocks until the oldest job is done
        futures.append(executor.submit(func, item))

    # Step 3: Drain the remaining jobs in the deque
    while futures:
        yield futures.popleft().result()


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

    def pixels_to_pdf_page(
        self,
        untrusted_data: bytes,
        untrusted_width: int,
        untrusted_height: int,
    ) -> fitz.Document:
        """Convert a byte array of RGB pixels into a PDF page"""
        pixmap = fitz.Pixmap(
            fitz.Colorspace(fitz.CS_RGB),
            untrusted_width,
            untrusted_height,
            untrusted_data,
            False,
        )
        pixmap.set_dpi(DEFAULT_DPI, DEFAULT_DPI)

        page_doc = fitz.Document()
        page_doc.insert_file(pixmap)
        page_pdf_bytes = page_doc.tobytes(deflate_images=True)

        return fitz.open("pdf", page_pdf_bytes)

    def pool_setup(self):
        avail_workers = mp.cpu_count() - 1
        max_workers = int(os.environ.get("DZ_POOL_WORKERS", avail_workers))
        print(f"DZ: Will use {max_workers} workers")
        pool_type = os.environ.get("DZ_POOL_TYPE", "process")
        if pool_type == "thread":
            pool_cls = ThreadPoolExecutor
        elif pool_type == "process":
            pool_cls = ProcessPoolExecutor
        else:
            raise Exception("What are you smoking man?")
        print(f"DZ: Will use {pool_cls} pool")

        ocr_pool = pool_cls(
            max_workers=max_workers,
            initializer=_ocr_pool_initializer,
            # mp_context=mp.get_context("forkserver"),
        )
        return ocr_pool

    def iter_untrusted_pixels(self, p, n_pages):
        for page in range(1, n_pages + 1):
            # Consume each page of the rasterizer's output...
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

            yield {
                "page": page,
                "width": width,
                "height": height,
                "num_pixels": num_pixels,
                "untrusted_pixels": untrusted_pixels,
                "tessdata_dir": str(get_tessdata_dir()),
                "ocr_lang": "eng",  # FIXME: I was too bored to do this the right way.
            }

    def convert_with_proc(
        self,
        document: Document,
        ocr_lang: Optional[str],
        p: subprocess.Popen,
    ) -> None:
        percentage = 0.0
        # Write the content of the to-be-converted document to the stdin of
        # the conversion process.
        with open(document.input_filename, "rb") as f:
            try:
                assert p.stdin is not None
                p.stdin.write(f.read())
                p.stdin.close()
            except BrokenPipeError:
                raise errors.ConverterProcException()

            # And read the stdout, which should contain the pixel buffers
            assert p.stdout
            n_pages = read_int(p.stdout)
            if n_pages == 0 or n_pages > errors.MAX_PAGES:
                raise errors.MaxPagesException()
            step = 100 / n_pages

            safe_doc = fitz.Document()

        pool = self.pool_setup()
        worker_fn = worker_ocr if ocr_lang else worker_deflate

        searchable = "searchable " if ocr_lang else ""

        def _iter_untrusted_pixels():
            return self.iter_untrusted_pixels(p, n_pages)

        queue_depth = int(os.environ.get("DZ_QUEUE_DEPTH", 2 * pool._max_workers))
        total_elapsed = 0
        print(f"DZ: Queue depth: {queue_depth}")
        print("DZ: Here we go...")

        start = time.perf_counter()
        for page, (elapsed, page_pdf_bytes) in enumerate(
            bounded_map(pool, worker_fn, _iter_untrusted_pixels(), queue_depth)
        ):
            total_elapsed += elapsed
            page_pdf = fitz.open("pdf", page_pdf_bytes)
            safe_doc.insert_pdf(page_pdf)
            text = f"Converted page {page}/{n_pages} from pixels to {searchable}PDF"
            self.print_progress(document, False, text, percentage)
            percentage += step

        end = time.perf_counter()
        print(f"DZ: Finished in: {(end - start):.4f}")
        print(f"DZ: Total worker time {total_elapsed:.4f}")

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
