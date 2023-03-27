#!/usr/bin/env python3
"""
Here are the steps, with progress bar percentages for each step:

document_to_pixels
- 0%-3%: Convert document into a PDF (skipped if the input file is a PDF)
- 3%-5%: Split PDF into individual pages, and count those pages
- 5%-50%: Convert each page into pixels (each page takes 45/n%, where n is the number of pages)

pixels_to_pdf:
- 50%-95%: Convert each page of pixels into a PDF (each page takes 45/n%, where n is the number of pages)
- 95%-100%: Compress the final PDF
"""

import asyncio
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple, Union

import magic

TIMEOUT_PER_PAGE: float = 30  # (seconds)
TIMEOUT_PER_MB: float = 30  # (seconds)
TIMEOUT_MIN: float = 60  # (seconds)


async def read_stream(
    sr: asyncio.StreamReader, callback: Optional[Callable] = None
) -> bytes:
    """Consume a byte stream line-by-line.

    Read all lines in a stream until EOF. If a user has passed a callback, call it for
    each line.

    Note that the lines are in bytes, since we can't assume that all command output will
    be UTF-8 encoded. Higher level commands are advised to decode the output to Unicode,
    if they know its encoding.
    """
    buf = b""
    while True:
        line = await sr.readline()
        if sr.at_eof():
            break
        if callback is not None:
            callback(line)
        # TODO: This would be a good place to log the received line, mostly for debug
        # logging.
        buf += line
    return buf


async def run_command(
    args: List[str],
    *,
    error_message: str,
    timeout_message: str,
    timeout: Optional[float],
    stdout_callback: Optional[Callable] = None,
    stderr_callback: Optional[Callable] = None,
) -> Tuple[bytes, bytes]:
    """Run a command and get its output.

    Run a command using asyncio.subprocess, consume its standard streams, and return its
    output in bytes.

    :raises RuntimeError: if the process returns a non-zero exit status
    :raises TimeoutError: if the process times out
    """
    # Start the provided command, and return a handle. The command will run in the
    # background.
    proc = await asyncio.subprocess.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    assert proc.stdout is not None
    assert proc.stderr is not None

    # Create asynchronous tasks that will consume the standard streams of the command,
    # and call callbacks if necessary.
    stdout_task = asyncio.create_task(read_stream(proc.stdout, stdout_callback))
    stderr_task = asyncio.create_task(read_stream(proc.stderr, stderr_callback))

    # Wait until the command has finished, for a specific timeout. Then, verify that the
    # command has completed successfully. In any other case, raise an exception.
    try:
        ret = await asyncio.wait_for(proc.wait(), timeout=timeout)
    except asyncio.exceptions.TimeoutError:
        raise TimeoutError(timeout_message)
    if ret != 0:
        raise RuntimeError(error_message)

    # Wait until the tasks that consume the command's standard streams have exited as
    # well, and return their output.
    stdout = await stdout_task
    stderr = await stderr_task
    return (stdout, stderr)


class DangerzoneConverter:
    def __init__(self) -> None:
        self.percentage: float = 0.0

    def calculate_timeout(
        self, size: float, pages: Optional[float] = None
    ) -> Optional[float]:
        """Calculate the timeout for a command.

        The timeout calculation takes two factors in mind:

        1. The size (in MiBs) of the dataset (document, multiple pages).
        2. The number of pages in the dataset.

        It then calculates proportional timeout values based on the above, and keeps the
        large one.  This way, we can handle several corner cases:

        * Documents with lots of pages, but small file size.
        * Single images with large file size.
        """
        if not int(os.environ.get("ENABLE_TIMEOUTS", 1)):
            return None

        # Do not have timeouts lower than 10 seconds, if the file size is small, since
        # we need to take into account the program's startup time as well.
        timeout = max(TIMEOUT_PER_MB * size, TIMEOUT_MIN)
        if pages:
            timeout = max(timeout, TIMEOUT_PER_PAGE * pages)
        return timeout

    async def document_to_pixels(self) -> None:
        conversions: Dict[str, Dict[str, Optional[str]]] = {
            # .pdf
            "application/pdf": {"type": None},
            # .docx
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
                "type": "libreoffice",
            },
            # .doc
            "application/msword": {
                "type": "libreoffice",
            },
            # .docm
            "application/vnd.ms-word.document.macroEnabled.12": {
                "type": "libreoffice",
            },
            # .xlsx
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                "type": "libreoffice",
            },
            # .xls
            "application/vnd.ms-excel": {
                "type": "libreoffice",
            },
            # .pptx
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": {
                "type": "libreoffice",
            },
            # .ppt
            "application/vnd.ms-powerpoint": {
                "type": "libreoffice",
            },
            # .odt
            "application/vnd.oasis.opendocument.text": {
                "type": "libreoffice",
            },
            # .odg
            "application/vnd.oasis.opendocument.graphics": {
                "type": "libreoffice",
            },
            # .odp
            "application/vnd.oasis.opendocument.presentation": {
                "type": "libreoffice",
            },
            # .ods
            "application/vnd.oasis.opendocument.spreadsheet": {
                "type": "libreoffice",
            },
            # .ods / .ots
            "application/vnd.oasis.opendocument.spreadsheet-template": {
                "type": "libreoffice",
            },
            # .odt / .ott
            "application/vnd.oasis.opendocument.text-template": {
                "type": "libreoffice",
            },
            # At least .odt, .docx, .odg, .odp, .ods, and .pptx
            "application/zip": {
                "type": "libreoffice",
            },
            # At least .doc, .docx, .odg, .odp, .odt, .pdf, .ppt, .pptx, .xls, and .xlsx
            "application/octet-stream": {
                "type": "libreoffice",
            },
            # At least .doc, .ppt, and .xls
            "application/x-ole-storage": {
                "type": "libreoffice",
            },
            # .jpg
            "image/jpeg": {"type": "convert"},
            # .gif
            "image/gif": {"type": "convert"},
            # .png
            "image/png": {"type": "convert"},
            # .tif
            "image/tiff": {"type": "convert"},
            "image/x-tiff": {"type": "convert"},
        }

        # Detect MIME type
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file("/tmp/input_file")

        # Validate MIME type
        if mime_type not in conversions:
            raise ValueError("The document format is not supported")

        # Get file size (in MiB)
        size = os.path.getsize("/tmp/input_file") / 1024**2

        # Calculate timeout for the first few file operations. The difference with the
        # subsequent ones is that we don't know the number of pages, before we have a
        # PDF at hand, so we rely on size heuristics.
        timeout = self.calculate_timeout(size)

        # Convert input document to PDF
        conversion = conversions[mime_type]
        if conversion["type"] is None:
            pdf_filename = "/tmp/input_file"
        elif conversion["type"] == "libreoffice":
            self.update_progress("Converting to PDF using LibreOffice")
            args = [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                "/tmp",
                "/tmp/input_file",
            ]
            await run_command(
                args,
                error_message="Conversion to PDF with LibreOffice failed",
                timeout_message=(
                    "Error converting document to PDF, LibreOffice timed out after"
                    f" {timeout} seconds"
                ),
                timeout=timeout,
            )
            pdf_filename = "/tmp/input_file.pdf"
        elif conversion["type"] == "convert":
            self.update_progress("Converting to PDF using GraphicsMagick")
            args = [
                "gm",
                "convert",
                "/tmp/input_file",
                "/tmp/input_file.pdf",
            ]
            await run_command(
                args,
                error_message="Conversion to PDF with GraphicsMagick failed",
                timeout_message=(
                    "Error converting document to PDF, GraphicsMagick timed out after"
                    f" {timeout} seconds"
                ),
                timeout=timeout,
            )
            pdf_filename = "/tmp/input_file.pdf"
        else:
            raise ValueError(
                f"Invalid conversion type {conversion['type']} for MIME type {mime_type}"
            )
        self.percentage += 3

        # Obtain number of pages
        self.update_progress("Calculating number of pages")
        stdout, _ = await run_command(
            ["pdfinfo", pdf_filename],
            error_message="PDF file is corrupted",
            timeout_message=(
                f"Extracting metadata from PDF timed out after {timeout} second"
            ),
            timeout=timeout,
        )

        search = re.search(r"Pages:\s*(\d+)\s*\n", stdout.decode())
        if search is not None:
            num_pages: int = int(search.group(1))
        else:
            raise ValueError("Number of pages could not be extracted from PDF")

        # Get a more precise timeout, based on the number of pages
        timeout = self.calculate_timeout(size, num_pages)

        def pdftoppm_progress_callback(line: bytes) -> None:
            """Function called for every line the 'pdftoppm' command outputs

            Sample pdftoppm output:

                $ pdftoppm sample.pdf  /tmp/safe -progress
                1 4 /tmp/safe-1.ppm
                2 4 /tmp/safe-2.ppm
                3 4 /tmp/safe-3.ppm
                4 4 /tmp/safe-4.ppm

            Each successful line is in the format "{page} {page_num} {ppm_filename}"
            """
            try:
                (page_str, num_pages_str, _) = line.decode().split()
                num_pages = int(num_pages_str)
                page = int(page_str)
            except ValueError as e:
                # Ignore all non-progress related output, since pdftoppm sends
                # everything to stderr and thus, errors can't be distinguished
                # easily. We rely instead on the exit code.
                return

            percentage_per_page = 45.0 / num_pages
            self.percentage += percentage_per_page
            self.update_progress(f"Converting page {page}/{num_pages} to pixels")

            zero_padding = "0" * (len(num_pages_str) - len(page_str))
            ppm_filename = f"{page_base}-{zero_padding}{page}.ppm"
            rgb_filename = f"{page_base}-{page}.rgb"
            width_filename = f"{page_base}-{page}.width"
            height_filename = f"{page_base}-{page}.height"
            filename_base = f"{page_base}-{page}"

            with open(ppm_filename, "rb") as f:
                # NOTE: PPM files have multiple ways of writing headers.
                # For our specific case we parse it expecting the header format that ppmtopdf produces
                # More info on PPM headers: https://people.uncw.edu/tompkinsj/112/texnh/assignments/imageFormat.html

                # Read the header
                header = f.readline().decode().strip()
                if header != "P6":
                    raise ValueError("Invalid PPM header")

                # Save the width and height
                dims = f.readline().decode().strip()
                width, height = dims.split()
                with open(width_filename, "w") as width_file:
                    width_file.write(width)
                with open(height_filename, "w") as height_file:
                    height_file.write(height)

                maxval = int(f.readline().decode().strip())
                # Check that the depth is 8
                if maxval != 255:
                    raise ValueError("Invalid PPM depth")

                data = f.read()

            # Save pixel data
            with open(rgb_filename, "wb") as f:
                f.write(data)

            # Delete the ppm file
            os.remove(ppm_filename)

        page_base = "/tmp/page"

        await run_command(
            [
                "pdftoppm",
                pdf_filename,
                page_base,
                "-progress",
            ],
            error_message="Conversion from PDF to PPM failed",
            timeout_message=(
                f"Error converting from PDF to PPM, pdftoppm timed out after {timeout}"
                " seconds"
            ),
            stderr_callback=pdftoppm_progress_callback,
            timeout=timeout,
        )

        self.update_progress("Converted document to pixels")

        # Move converted files into /dangerzone
        for filename in (
            glob.glob("/tmp/page-*.rgb")
            + glob.glob("/tmp/page-*.width")
            + glob.glob("/tmp/page-*.height")
        ):
            shutil.move(filename, "/dangerzone")

    async def pixels_to_pdf(self) -> None:
        self.percentage = 50.0

        num_pages = len(glob.glob("/dangerzone/page-*.rgb"))
        total_size = 0.0

        # Convert RGB files to PDF files
        percentage_per_page = 45.0 / num_pages
        for page in range(1, num_pages + 1):
            filename_base = f"/dangerzone/page-{page}"
            rgb_filename = f"{filename_base}.rgb"
            width_filename = f"{filename_base}.width"
            height_filename = f"{filename_base}.height"
            png_filename = f"/tmp/page-{page}.png"
            ocr_filename = f"/tmp/page-{page}"
            pdf_filename = f"/tmp/page-{page}.pdf"

            with open(width_filename) as f:
                width = f.read().strip()
            with open(height_filename) as f:
                height = f.read().strip()

            # The first few operations happen on a per-page basis.
            page_size = os.path.getsize(filename_base + ".rgb") / 1024**2
            total_size += page_size
            timeout = self.calculate_timeout(page_size, 1)

            if os.environ.get("OCR") == "1":  # OCR the document
                self.update_progress(
                    f"Converting page {page}/{num_pages} from pixels to searchable PDF"
                )
                await run_command(
                    [
                        "gm",
                        "convert",
                        "-size",
                        f"{width}x{height}",
                        "-depth",
                        "8",
                        f"rgb:{rgb_filename}",
                        f"png:{png_filename}",
                    ],
                    error_message=f"Page {page}/{num_pages} conversion to PNG failed",
                    timeout_message=(
                        "Error converting pixels to PNG, convert timed out after"
                        f" {timeout} seconds"
                    ),
                    timeout=timeout,
                )
                await run_command(
                    [
                        "tesseract",
                        png_filename,
                        ocr_filename,
                        "-l",
                        os.environ.get("OCR_LANGUAGE"),  # type: ignore
                        "--dpi",
                        "70",
                        "pdf",
                    ],
                    error_message=f"Page {page}/{num_pages} OCR failed",
                    timeout_message=(
                        "Error converting PNG to searchable PDF, tesseract timed out"
                        f" after {timeout} seconds"
                    ),
                    timeout=timeout,
                )

            else:  # Don't OCR
                self.update_progress(
                    f"Converting page {page}/{num_pages} from pixels to PDF"
                )
                await run_command(
                    [
                        "gm",
                        "convert",
                        "-size",
                        f"{width}x{height}",
                        "-depth",
                        "8",
                        f"rgb:{rgb_filename}",
                        f"pdf:{pdf_filename}",
                    ],
                    error_message=f"Page {page}/{num_pages} conversion to PDF failed",
                    timeout_message=(
                        "Error converting RGB to PDF, convert timed out after"
                        f" {timeout} seconds"
                    ),
                    timeout=timeout,
                )

            self.percentage += percentage_per_page

        # Next operations apply to the all the pages, so we need to recalculate the
        # timeout.
        timeout = self.calculate_timeout(total_size, num_pages)

        # Merge pages into a single PDF
        self.update_progress(f"Merging {num_pages} pages into a single PDF")
        args = ["pdfunite"]
        for page in range(1, num_pages + 1):
            args.append(f"/tmp/page-{page}.pdf")
        args.append(f"/tmp/safe-output.pdf")
        await run_command(
            args,
            error_message="Merging pages into a single PDF failed",
            timeout_message=(
                "Error merging pages into a single PDF, pdfunite timed out after"
                f" {timeout} seconds"
            ),
            timeout=timeout,
        )

        self.percentage += 2

        # Compress
        self.update_progress("Compressing PDF")
        await run_command(
            ["ps2pdf", "/tmp/safe-output.pdf", "/tmp/safe-output-compressed.pdf"],
            error_message="Compressing PDF failed",
            timeout_message=(
                f"Error compressing PDF, ps2pdf timed out after {timeout} seconds"
            ),
            timeout=timeout,
        )

        self.percentage = 100.0
        self.update_progress("Safe PDF created")

        # Move converted files into /safezone
        shutil.move("/tmp/safe-output.pdf", "/safezone")
        shutil.move("/tmp/safe-output-compressed.pdf", "/safezone")

    def update_progress(self, text: str, *, error: bool = False) -> None:
        print(
            json.dumps(
                {"error": error, "text": text, "percentage": int(self.percentage)}
            )
        )
        sys.stdout.flush()


async def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} [document-to-pixels]|[pixels-to-pdf]")
        return -1

    converter = DangerzoneConverter()

    try:
        if sys.argv[1] == "document-to-pixels":
            await converter.document_to_pixels()
        elif sys.argv[1] == "pixels-to-pdf":
            await converter.pixels_to_pdf()
    except (RuntimeError, TimeoutError, ValueError) as e:
        converter.update_progress(str(e), error=True)
        return 1
    else:
        return 0  # Success!


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
