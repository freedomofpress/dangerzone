import contextlib
import logging
import multiprocessing as mp
import os
import platform
import signal
import subprocess
import sys
import threading
from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from io import BytesIO
from typing import IO, Callable, Iterator, List, Optional

import fitz
from colorama import Fore, Style

from ..conversion import errors
from ..conversion.common import (
    DEFAULT_DPI,
    FILETYPE_AUDIO,
    FILETYPE_DOCUMENT,
    FILETYPE_IMAGE,
    FILETYPE_VIDEO,
    INT_BYTES,
)
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


def _ocr_page_worker(
    pixmap_bytes: bytes,
    width: int,
    height: int,
    ocr_lang: str,
    tessdata_dir: str,
) -> bytes:
    """Worker function for multiprocessing OCR. Returns PDF bytes."""
    try:
        pixmap = fitz.Pixmap(
            fitz.Colorspace(fitz.CS_RGB),
            width,
            height,
            pixmap_bytes,
            False,
        )
        pixmap.set_dpi(DEFAULT_DPI, DEFAULT_DPI)
        return pixmap.pdfocr_tobytes(
            compress=True,
            language=ocr_lang,
            tessdata=tessdata_dir,
        )
    except Exception as e:
        # Re-raise with a picklable exception to avoid multiprocessing errors
        # when the original exception contains unpicklable SWIG objects
        raise RuntimeError(str(e)) from None


def _stream_stderr(process_stderr: IO[bytes], stderr_buf: IO[bytes]) -> None:
    """Helper to stream stderr from a process to a buffer."""
    try:
        for line in process_stderr:
            stderr_buf.write(line)
    except (ValueError, IOError) as e:
        log.debug(f"Stderr stream closed: {e}")


def _drain_ocr_futures(
    ocr_futures: deque,
    safe_doc: fitz.Document,
    counter: List[int],
    n_pages: int,
    document: Document,
    print_progress: Callable,
    file_info: Optional[tuple] = None,
    block_until_below: Optional[int] = None,
) -> None:
    """
    Collect completed OCR pages (from the front of the queue)
    and append them to the resulting safe_doc.

    If block_until_below is set, wait on futures until the
    queue size drops below that threshold.
    """
    while ocr_futures:
        if block_until_below is not None and len(ocr_futures) <= block_until_below:
            break
        _, future = ocr_futures[0]
        if not future.done():
            if block_until_below is None:
                break  # non-blocking: stop at first incomplete
            future.result()  # blocking: wait for the future to complete
        _, future = ocr_futures.popleft()
        page_pdf_bytes = future.result()
        page_doc = fitz.open("pdf", page_pdf_bytes)
        safe_doc.insert_pdf(page_doc)
        counter[0] += 1
        ocr_page_num = counter[0]

        if file_info:
            file_index, total_files, file_step, base_percentage, display_filename = (
                file_info
            )
            text = (
                f"Converted file {file_index + 1}/{total_files} ({display_filename}), "
                f"page {ocr_page_num}/{n_pages} to searchable PDF"
            )
            page_percentage = (ocr_page_num / n_pages) * file_step
            print_progress(document, False, text, base_percentage + page_percentage)
        else:
            ocr_percentage = (ocr_page_num / n_pages) * 100
            text = f"Converted page {ocr_page_num}/{n_pages} to searchable PDF"
            print_progress(document, False, text, ocr_percentage)


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
            with self.doc_to_pixels_sandbox(document) as conversion_proc:
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

    @abstractmethod
    def start_exec(
        self,
        document: Document,
        command: List[str],
        stdin: Optional[int] = subprocess.PIPE,
    ) -> subprocess.Popen:
        pass

    @contextlib.contextmanager
    def run_exec(
        self,
        document: Document,
        command: List[str],
        stdin: Optional[int] = subprocess.PIPE,
    ) -> Iterator[subprocess.Popen]:
        """Run a command in the sandbox, capture stderr, and yield the process."""
        stderr = BytesIO()
        p = self.start_exec(document, command, stdin)
        stderr_thread = self.start_stderr_thread(p, stderr)

        try:
            yield p
        finally:
            # Ensure the process has exited
            p.wait()

            if stderr_thread:
                stderr_thread.join(timeout=1)
                debug_bytes = stderr.getvalue()
                debug_log = sanitize_debug_text(debug_bytes)
                incomplete = "(incomplete) " if stderr_thread.is_alive() else ""

                if command[0] == "index":
                    desc = "Indexing"
                elif command[0] == "sanitize" and len(command) > 1:
                    filename = replace_control_chars(os.path.basename(command[1]))
                    desc = f"Conversion ({filename})"
                else:
                    desc = f"Exec ({' '.join(command)})"

                log.info(
                    f"{desc} output\n"
                    f"----- {desc.upper()} LOG START {incomplete}-----\n"
                    f"{debug_log}"
                    f"----- {desc.upper()} LOG END -----"
                )

    def _get_index(self, document: Document) -> List[tuple[str, int]]:
        """Run the 'index' command and return the list of (filename, type) to sanitize."""
        self.print_progress(document, False, "Indexing archive", 0)
        with open(document.input_filename, "rb") as f:
            with self.run_exec(document, ["index"]) as index_proc:
                try:
                    assert index_proc.stdin is not None
                    index_proc.stdin.write(f.read())
                    index_proc.stdin.close()
                except BrokenPipeError:
                    raise errors.ConverterProcException()

                assert index_proc.stdout
                try:
                    n_files = read_int(index_proc.stdout)
                except errors.ConverterProcException:
                    # Command might have failed
                    ret = index_proc.wait()
                    if ret != 0:
                        raise errors.exception_from_error_code(ret)
                    raise

                index = []
                for _ in range(n_files):
                    file_type = int.from_bytes(
                        read_bytes(index_proc.stdout, 1), "big"
                    )
                    filename_len = read_int(index_proc.stdout)
                    filename = read_bytes(index_proc.stdout, filename_len).decode()
                    index.append((filename, file_type))

                index_proc.wait()
        return index

    def _convert_audio(
        self,
        document: Document,
        filename: str,
        output_filename: str,
        file_index: int,
        total_files: int,
    ) -> None:
        display_filename = replace_control_chars(os.path.basename(filename))
        log.debug(f"Sanitizing audio file {file_index + 1}/{total_files}: {filename}")
        
        file_step = 100 / total_files
        base_percentage = file_index * file_step
        
        self.print_progress(
            document, False, f"Sanitizing audio ({display_filename})", base_percentage
        )

        with self.run_exec(document, ["sanitize", "--audio-only", filename]) as sanitize_proc:
            assert sanitize_proc.stdout is not None
            
            # Local ffmpeg to encode raw PCM to safe MKV (Opus)
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-f", "s16le",
                "-ar", "44100",
                "-ac", "2",
                "-i", "-",
                "-c:a", "libopus",
                output_filename
            ]
            
            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stderr=self.proc_stderr,
            )
            assert ffmpeg_proc.stdin is not None
            
            try:
                while True:
                    chunk = sanitize_proc.stdout.read(65536)
                    if not chunk:
                        break
                    ffmpeg_proc.stdin.write(chunk)
            finally:
                ffmpeg_proc.stdin.close()
                ffmpeg_proc.wait()
                if ffmpeg_proc.returncode != 0:
                    raise errors.ConversionException("Local audio encoding failed")

    def _convert_video(
        self,
        document: Document,
        filename: str,
        output_filename: str,
        file_index: int,
        total_files: int,
    ) -> None:
        display_filename = replace_control_chars(os.path.basename(filename))
        log.debug(f"Sanitizing video file {file_index + 1}/{total_files}: {filename}")
        
        file_step = 100 / total_files
        base_percentage = file_index * file_step
        
        self.print_progress(
            document, False, f"Sanitizing video ({display_filename})", base_percentage
        )

        # Create pipes
        r_audio, w_audio = os.pipe()
        r_video, w_video = os.pipe()

        # Start parallel sanitize commands
        p_video = self.start_exec(document, ["sanitize", "--video-only", filename])
        p_audio = self.start_exec(document, ["sanitize", "--audio-only", filename])

        assert p_video.stdout is not None
        assert p_audio.stdout is not None

        # Read video metadata from p_video.stdout
        try:
            width = read_int(p_video.stdout)
            height = read_int(p_video.stdout)
            fps = read_int(p_video.stdout)
        except errors.ConverterProcException:
            # Check for errors in processes
            terminate_process_group(p_video)
            terminate_process_group(p_audio)
            os.close(r_audio)
            os.close(w_audio)
            os.close(r_video)
            os.close(w_video)
            raise

        # Local ffmpeg to encode raw PCM and RGB to safe WebM (VP9/Opus)
        if platform.system() != "Windows":
            audio_input = f"/dev/fd/{r_audio}"
            video_input = f"/dev/fd/{r_video}"
        else:
            # On Windows, we'll try to use pipe:X but it's fragile.
            # For now, let's use the FD numbers.
            audio_input = f"pipe:{r_audio}"
            video_input = f"pipe:{r_video}"
        
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "s16le", "-ar", "44100", "-ac", "2", "-i", audio_input,
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", video_input,
            "-c:v", "libvpx-vp9", "-c:a", "libopus",
            "-crf", "30", "-b:v", "0", # VP9 recommended settings for quality
            output_filename
        ]

        import threading
        
        def pipe_thread(src, dst_fd):
            with os.fdopen(dst_fd, "wb") as dst:
                try:
                    while True:
                        chunk = src.read(65536)
                        if not chunk:
                            break
                        dst.write(chunk)
                except (IOError, BrokenPipeError):
                    pass

        try:
            # We must make the read ends inheritable
            if platform.system() == "Windows":
                # On Windows, we use handle inheritance
                os.set_handle_inheritable(r_audio, True)
                os.set_handle_inheritable(r_video, True)
            
            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE, # FD 0, unused
                stderr=self.proc_stderr,
                pass_fds=(r_audio, r_video) if platform.system() != "Windows" else [],
            )
            
            # Actually, I'll use a helper to pipe from sanitize to the write end of the pipes
            t_audio = threading.Thread(target=pipe_thread, args=(p_audio.stdout, w_audio))
            t_video = threading.Thread(target=pipe_thread, args=(p_video.stdout, w_video))
            
            t_audio.start()
            t_video.start()
            
            ffmpeg_proc.wait()
            
            t_audio.join()
            t_video.join()
            
            p_audio.wait()
            p_video.wait()
            
            if ffmpeg_proc.returncode != 0:
                raise errors.ConversionException("Local video encoding failed")
        finally:
            os.close(r_audio)
            os.close(r_video)
            # w_audio and w_video are closed in the threads
            
            terminate_process_group(p_audio)
            terminate_process_group(p_video)

    def _convert_file(
        self,
        document: Document,
        filename: str,
        ocr_lang: Optional[str],
        safe_doc: fitz.Document,
        file_index: int,
        total_files: int,
    ) -> bool:
        """Sanitize a single file. Returns True if successful, False if unsupported (logged as warning)."""
        display_filename = replace_control_chars(os.path.basename(filename))
        log.debug(f"Sanitizing file {file_index + 1}/{total_files}: {filename}")

        with self.run_exec(document, ["sanitize", filename]) as sanitize_proc:
            assert sanitize_proc.stdout
            try:
                n_pages = read_int(sanitize_proc.stdout)
            except errors.ConverterProcException:
                ret = sanitize_proc.wait()
                if ret != 0:
                    try:
                        raise errors.exception_from_error_code(ret)
                    except errors.DocFormatUnsupported:
                        log.warning(f"Skipping unsupported file: {display_filename}")
                        return False
                    except errors.ConversionException:
                        raise
                raise

            if n_pages == 0 or n_pages > errors.MAX_PAGES:
                raise errors.MaxPagesException()

            # Global progress: each file takes 100 / total_files percent
            file_step = 100 / total_files
            base_percentage = file_index * file_step

            # If we are doing OCR, start a pool of workers to do it in parallel
            if ocr_lang:
                max_workers = max(1, round(mp.cpu_count() / 2))
                ocr_pool = ProcessPoolExecutor(
                    max_workers=max_workers,
                    initializer=_ocr_pool_initializer,
                    mp_context=mp.get_context("spawn"),
                )
                # Pre-compute tessdata path to pass to workers (they can't access
                # sys.dangerzone_dev which is set only in the main process)
                tessdata_dir = str(get_tessdata_dir())
                ocr_futures: deque = deque()  # stores (page_num, future) tuples
                ocr_page_num_counter = [0]  # tracks how many pages have completed OCR
                file_info = (
                    file_index,
                    total_files,
                    file_step,
                    base_percentage,
                    display_filename,
                )
            else:
                ocr_pool = None
                tessdata_dir = None

            try:
                for page in range(1, n_pages + 1):
                    # Block if too many pages are waiting for OCR, to avoid
                    # filling RAM with pixel buffers from the sandbox.
                    # Wait until the queue drains to the number of workers
                    # before resuming.
                    if ocr_lang and len(ocr_futures) >= 2 * max_workers:
                        _drain_ocr_futures(
                            ocr_futures,
                            safe_doc,
                            ocr_page_num_counter,
                            n_pages,
                            document,
                            self.print_progress,
                            file_info=file_info,
                            block_until_below=max_workers,
                        )

                    # Consume each page of the rasterizer's output...
                    width = read_int(sanitize_proc.stdout)
                    height = read_int(sanitize_proc.stdout)
                    if not (1 <= width <= errors.MAX_PAGE_WIDTH):
                        raise errors.MaxPageWidthException()
                    if not (1 <= height <= errors.MAX_PAGE_HEIGHT):
                        raise errors.MaxPageHeightException()

                    num_pixels = width * height * 3  # three color channels
                    untrusted_pixels = read_bytes(
                        sanitize_proc.stdout,
                        num_pixels,
                    )

                    # ... and send them to the OCR worker pool...
                    if ocr_lang:
                        assert ocr_pool is not None
                        assert tessdata_dir is not None
                        future = ocr_pool.submit(
                            _ocr_page_worker,
                            untrusted_pixels,
                            width,
                            height,
                            ocr_lang,
                            tessdata_dir,
                        )
                        ocr_futures.append((page, future))

                        # Non-blocking drain of any completed futures
                        _drain_ocr_futures(
                            ocr_futures,
                            safe_doc,
                            ocr_page_num_counter,
                            n_pages,
                            document,
                            self.print_progress,
                            file_info=file_info,
                        )
                    else:
                        # ... Or process immediately (if no OCR is requested)
                        page_pdf = self.pixels_to_pdf_page(
                            untrusted_pixels,
                            width,
                            height,
                        )
                        safe_doc.insert_pdf(page_pdf)

                        searchable = "searchable " if ocr_lang else ""
                        text = (
                            f"Converting file {file_index + 1}/{total_files} ({display_filename}), "
                            f"page {page}/{n_pages} from pixels to {searchable}PDF"
                        )
                        page_percentage = (page / n_pages) * file_step
                        self.print_progress(
                            document, False, text, base_percentage + page_percentage
                        )

                # Once all pages have been submitted, wait for remaining futures
                if ocr_lang:
                    _drain_ocr_futures(
                        ocr_futures,
                        safe_doc,
                        ocr_page_num_counter,
                        n_pages,
                        document,
                        self.print_progress,
                        file_info=file_info,
                        block_until_below=0,
                    )

            finally:
                if ocr_pool is not None:
                    ocr_pool.shutdown()

            sanitize_proc.stdout.close()
            ret = sanitize_proc.wait()
            if ret != 0:
                try:
                    raise errors.exception_from_error_code(ret)
                except errors.DocFormatUnsupported:
                    log.warning(f"Skipping unsupported file: {display_filename}")
                    return False
                except errors.ConversionException:
                    raise
        return True

    def convert_with_proc(
        self,
        document: Document,
        ocr_lang: Optional[str],
        p: subprocess.Popen,
    ) -> None:
        index = self._get_index(document)
        n_files = len(index)

        if n_files == 0:
            raise errors.DocCorruptedException("Archive is empty")

        # Protocol: if first file starts with /, it's an archive
        is_archive_mode = index[0][0].startswith("/")

        if not is_archive_mode:
            # Single file mode (existing behavior)
            filename, file_type = index[0]
            if file_type in [FILETYPE_DOCUMENT, FILETYPE_IMAGE]:
                safe_doc = fitz.Document()
                success = self._convert_file(document, filename, ocr_lang, safe_doc, 0, 1)
                if not success:
                    # If the only file is unsupported, we fail
                    raise errors.DocFormatUnsupported()
                # Saving it with a different name first, because PyMuPDF cannot handle
                # non-Unicode chars.
                safe_doc.save(document.sanitized_output_filename)
                os.replace(document.sanitized_output_filename, document.output_filename)
            elif file_type == FILETYPE_AUDIO:
                self._convert_audio(document, filename, document.output_filename, 0, 1)
            elif file_type == FILETYPE_VIDEO:
                self._convert_video(document, filename, document.output_filename, 0, 1)
        else:
            # Archive mode: create a directory {name}-safe/ and put safe PDFs/media in it
            # Determine base path in container to calculate relative paths
            filenames = [item[0] for item in index]
            common_base = os.path.commonpath(filenames)
            
            # Host output directory
            input_base = os.path.splitext(document.input_filename)[0]
            output_dir = f"{input_base}-safe"
            os.makedirs(output_dir, exist_ok=True)

            for i, (filename, file_type) in enumerate(index):
                # Calculate relative path
                rel_path = os.path.relpath(filename, common_base)
                # Ensure no traversal (just in case)
                rel_path = os.path.normpath(rel_path)
                if rel_path.startswith("..") or os.path.isabs(rel_path):
                    log.warning(f"Skipping potentially dangerous path: {filename}")
                    continue

                # Host target file
                target_filename = os.path.join(output_dir, rel_path)
                
                if file_type in [FILETYPE_DOCUMENT, FILETYPE_IMAGE]:
                    # Ensure it ends in .pdf
                    if not target_filename.lower().endswith(".pdf"):
                        target_filename += ".pdf"
                    os.makedirs(os.path.dirname(target_filename), exist_ok=True)
                    safe_doc = fitz.Document()
                    success = self._convert_file(document, filename, ocr_lang, safe_doc, i, n_files)
                    if not success:
                        continue
                    sanitized_target = replace_control_chars(target_filename)
                    safe_doc.save(sanitized_target)
                    if sanitized_target != target_filename:
                        os.replace(sanitized_target, target_filename)
                elif file_type == FILETYPE_AUDIO:
                    # Ensure appropriate extension for safe output
                    if not target_filename.lower().endswith(".mkv"):
                        target_filename += ".mkv"
                    os.makedirs(os.path.dirname(target_filename), exist_ok=True)
                    self._convert_audio(document, filename, target_filename, i, n_files)
                elif file_type == FILETYPE_VIDEO:
                    # Ensure appropriate extension for safe output
                    if not target_filename.lower().endswith(".webm"):
                        target_filename += ".webm"
                    os.makedirs(os.path.dirname(target_filename), exist_ok=True)
                    self._convert_video(document, filename, target_filename, i, n_files)

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
    def start_doc_to_pixels_sandbox(self, document: Document) -> subprocess.Popen:
        pass

    @abstractmethod
    def terminate_doc_to_pixels_sandbox(
        self, document: Document, p: subprocess.Popen
    ) -> None:
        """Terminate gracefully the process started for the doc-to-pixels phase."""
        pass

    def ensure_stop_doc_to_pixels_sandbox(
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
        self.terminate_doc_to_pixels_sandbox(document, p)
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
    def doc_to_pixels_sandbox(
        self,
        document: Document,
        timeout_exception: int = TIMEOUT_EXCEPTION,
        timeout_grace: int = TIMEOUT_GRACE,
        timeout_force: int = TIMEOUT_FORCE,
    ) -> Iterator[subprocess.Popen]:
        """Start a conversion process, pass it to the caller, and then clean it up."""
        # Store the proc stderr in memory
        stderr = BytesIO()
        p = self.start_doc_to_pixels_sandbox(document)
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
            self.ensure_stop_doc_to_pixels_sandbox(
                document, p, timeout_grace=timeout_grace, timeout_force=timeout_force
            )

            if stderr_thread:
                # Wait for the thread to complete. If it's still alive, mention it in the debug log.
                stderr_thread.join(timeout=1)

                debug_bytes = stderr.getvalue()
                debug_log = sanitize_debug_text(debug_bytes)

                incomplete = "(incomplete) " if stderr_thread.is_alive() else ""

                log.info(
                    "Conversion output (sandbox)\n"
                    f"----- SANDBOX LOG START {incomplete}-----\n"
                    f"{debug_log}"  # no need for an extra newline here
                    "----- SANDBOX LOG END -----"
                )

    def start_stderr_thread(
        self, process: subprocess.Popen, stderr: IO[bytes]
    ) -> Optional[threading.Thread]:
        """Start a thread to read stderr from the process"""
        if process.stderr:
            stderr_thread = threading.Thread(
                target=_stream_stderr,
                args=(process.stderr, stderr),
                daemon=True,
            )
            stderr_thread.start()
            return stderr_thread
        return None
