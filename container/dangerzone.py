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

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Callable, Dict, List, Optional

import magic

# timeout in seconds for any single subprocess
DEFAULT_TIMEOUT: float = 120

# timeout in seconds for compressing a single page of the final document
COMPRESSION_TIMEOUT: float = 10


def run_command(
    args: List[str],
    *,
    error_message: str,
    timeout_message: str,
    timeout: float = DEFAULT_TIMEOUT,
    stdout_callback: Callable = None,
    stderr_callback: Callable = None,
) -> None:
    """
    Runs a command and returns the result.

    :raises RuntimeError: if the process returns a non-zero exit status
    :raises TimeoutError: if the process times out
    """
    if stdout_callback is None and stderr_callback is None:
        try:
            subprocess.run(args, timeout=timeout, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(error_message) from e
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(timeout_message) from e

    else:
        p = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        # Progress callback requires a manually implemented timeout
        start_time = time.time()

        # Make reading from stdout or stderr non-blocking
        if p.stdout:
            os.set_blocking(p.stdout.fileno(), False)
        if p.stderr:
            os.set_blocking(p.stderr.fileno(), False)

        while True:
            # Processes hasn't finished
            if p.poll() is not None:
                if p.returncode != 0:
                    raise RuntimeError(error_message)
                break

            # Check if timeout hasn't expired
            if time.time() - start_time > timeout:
                p.kill()
                raise TimeoutError(timeout_message)

            if p.stdout and stdout_callback is not None:
                line = p.stdout.readline()
                if len(line) > 0:
                    line = line.rstrip()  # strip trailing "\n"
                    stdout_callback(line)

            if p.stderr and stderr_callback is not None:
                line = p.stderr.readline()
                if len(line) > 0:
                    line = line.rstrip()  # strip trailing "\n"
                    stderr_callback(line)


class DangerzoneConverter:
    def __init__(self) -> None:
        self.percentage: float = 0.0

    def document_to_pixels(self) -> None:

        conversions: Dict[str, Dict[str, Optional[str]]] = {
            # .pdf
            "application/pdf": {"type": None},
            # .docx
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
                "type": "libreoffice",
                "libreoffice_output_filter": "writer_pdf_Export",
            },
            # .doc
            "application/msword": {
                "type": "libreoffice",
                "libreoffice_output_filter": "writer_pdf_Export",
            },
            # .docm
            "application/vnd.ms-word.document.macroEnabled.12": {
                "type": "libreoffice",
                "libreoffice_output_filter": "writer_pdf_Export",
            },
            # .xlsx
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                "type": "libreoffice",
                "libreoffice_output_filter": "calc_pdf_Export",
            },
            # .xls
            "application/vnd.ms-excel": {
                "type": "libreoffice",
                "libreoffice_output_filter": "calc_pdf_Export",
            },
            # .pptx
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": {
                "type": "libreoffice",
                "libreoffice_output_filter": "impress_pdf_Export",
            },
            # .ppt
            "application/vnd.ms-powerpoint": {
                "type": "libreoffice",
                "libreoffice_output_filter": "impress_pdf_Export",
            },
            # .odt
            "application/vnd.oasis.opendocument.text": {
                "type": "libreoffice",
                "libreoffice_output_filter": "writer_pdf_Export",
            },
            # .odg
            "application/vnd.oasis.opendocument.graphics": {
                "type": "libreoffice",
                "libreoffice_output_filter": "impress_pdf_Export",
            },
            # .odp
            "application/vnd.oasis.opendocument.presentation": {
                "type": "libreoffice",
                "libreoffice_output_filter": "impress_pdf_Export",
            },
            # .ops
            "application/vnd.oasis.opendocument.spreadsheet": {
                "type": "libreoffice",
                "libreoffice_output_filter": "calc_pdf_Export",
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
                f"pdf:{conversion['libreoffice_output_filter']}",
                "--outdir",
                "/tmp",
                "/tmp/input_file",
            ]
            run_command(
                args,
                error_message="Conversion to PDF with LibreOffice failed",
                timeout_message=f"Error converting document to PDF, LibreOffice timed out after {DEFAULT_TIMEOUT} seconds",
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
            run_command(
                args,
                error_message="Conversion to PDF with GraphicsMagick failed",
                timeout_message=f"Error converting document to PDF, GraphicsMagick timed out after {DEFAULT_TIMEOUT} seconds",
            )
            pdf_filename = "/tmp/input_file.pdf"
        else:
            raise ValueError(
                f"Invalid conversion type {conversion['type']} for MIME type {mime_type}"
            )
        self.percentage += 3

        self.update_progress("Obtaining PDF metadata")

        def pdftoppm_progress_callback(line: str) -> None:
            """Function called for every line the 'pdftoppm'command outputs

            Sample pdftoppm output:

                $ pdftoppm sample.pdf  /tmp/safe -progress
                1 4 /tmp/safe-1.ppm
                2 4 /tmp/safe-2.ppm
                3 4 /tmp/safe-3.ppm
                4 4 /tmp/safe-4.ppm

            Each successful line is in the format "{page} {page_num} {ppm_filename}"
            """
            try:
                (page_str, num_pages_str, _) = line.split()
                num_pages = int(num_pages_str)
                page = int(page_str)
            except ValueError as e:
                raise RuntimeError("Conversion from PDF to PPM failed") from e

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
        # Convert to PPM, which is essentially an RGB format
        run_command(
            [
                "pdftoppm",
                pdf_filename,
                page_base,
                "-progress",
            ],
            error_message="Conversion from PDF to PPM failed",
            timeout_message=f"Error converting from PDF to PPM, pdftoppm timed out after {DEFAULT_TIMEOUT} seconds",
            stderr_callback=pdftoppm_progress_callback,
        )

        self.update_progress("Converted document to pixels")

        # Move converted files into /dangerzone
        for filename in (
            glob.glob("/tmp/page-*.rgb")
            + glob.glob("/tmp/page-*.width")
            + glob.glob("/tmp/page-*.height")
        ):
            shutil.move(filename, "/dangerzone")

    def pixels_to_pdf(self) -> None:
        self.percentage = 50.0

        num_pages = len(glob.glob("/dangerzone/page-*.rgb"))

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

            if os.environ.get("OCR") == "1":  # OCR the document
                self.update_progress(
                    f"Converting page {page}/{num_pages} from pixels to searchable PDF"
                )
                run_command(
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
                    timeout_message=f"Error converting pixels to PNG, convert timed out after {DEFAULT_TIMEOUT} seconds",
                )
                run_command(
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
                    timeout_message=f"Error converting PNG to searchable PDF, tesseract timed out after {DEFAULT_TIMEOUT} seconds",
                )

            else:  # Don't OCR
                self.update_progress(
                    f"Converting page {page}/{num_pages} from pixels to PDF"
                )
                run_command(
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
                    timeout_message=f"Error converting RGB to PDF, convert timed out after {DEFAULT_TIMEOUT} seconds",
                )

            self.percentage += percentage_per_page

        # Merge pages into a single PDF
        self.update_progress(f"Merging {num_pages} pages into a single PDF")
        args = ["pdfunite"]
        for page in range(1, num_pages + 1):
            args.append(f"/tmp/page-{page}.pdf")
        args.append(f"/tmp/safe-output.pdf")
        run_command(
            args,
            error_message="Merging pages into a single PDF failed",
            timeout_message=f"Error merging pages into a single PDF, pdfunite timed out after {DEFAULT_TIMEOUT} seconds",
        )

        self.percentage += 2

        # Compress
        self.update_progress("Compressing PDF")
        compress_timeout = num_pages * COMPRESSION_TIMEOUT
        run_command(
            ["ps2pdf", "/tmp/safe-output.pdf", "/tmp/safe-output-compressed.pdf"],
            timeout_message=f"Error compressing PDF, ps2pdf timed out after {compress_timeout} seconds",
            error_message="Compressing PDF failed",
            timeout=compress_timeout,
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


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} [document-to-pixels]|[pixels-to-pdf]")
        return -1

    converter = DangerzoneConverter()

    try:
        if sys.argv[1] == "document-to-pixels":
            converter.document_to_pixels()
        elif sys.argv[1] == "pixels-to-pdf":
            converter.pixels_to_pdf()
    except (RuntimeError, TimeoutError, ValueError) as e:
        converter.update_progress(str(e), error=True)
        return 1
    else:
        return 0  # Success!


if __name__ == "__main__":
    sys.exit(main())
