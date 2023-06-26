#!/usr/bin/env python3
"""
Here are the steps, with progress bar percentages:

- 0%-3%: Convert document into a PDF (skipped if the input file is a PDF)
- 3%-5%: Split PDF into individual pages, and count those pages
- 5%-50%: Convert each page into pixels (each page takes 45/n%, where n is the number of pages)
"""

import asyncio
import glob
import os
import re
import shutil
import sys
from typing import Dict, Optional

import magic

from .common import DangerzoneConverter, run_command


class DocumentToPixels(DangerzoneConverter):
    async def convert(self) -> None:
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
            # .hwp
            "application/vnd.hancom.hwp": {
                "type": "libreoffice",
            },
            "application/haansofthwp": {
                "type": "libreoffice",
            },
            "application/x-hwp": {
                "type": "libreoffice",
            },
            # .hwpx
            "application/vnd.hancom.hwpx": {
                "type": "libreoffice",
            },
            "application/haansofthwpx": {
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
        try:
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file("/tmp/input_file")
        except TypeError:
            mime_type = magic.detect_from_filename("/tmp/input_file").mime_type

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
                "--safe-mode",
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

        # Move converted files into /tmp/dangerzone
        for filename in (
            glob.glob("/tmp/page-*.rgb")
            + glob.glob("/tmp/page-*.width")
            + glob.glob("/tmp/page-*.height")
        ):
            shutil.move(filename, "/tmp/dangerzone")


async def main() -> int:
    converter = DocumentToPixels()

    try:
        await converter.convert()
    except (RuntimeError, TimeoutError, ValueError) as e:
        converter.update_progress(str(e), error=True)
        return 1
    else:
        return 0  # Success!


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
