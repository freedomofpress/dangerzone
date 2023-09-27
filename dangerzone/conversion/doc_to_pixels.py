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
from typing import Dict, List, Optional

import magic

from . import errors
from .common import DangerzoneConverter, running_on_qubes


class DocumentToPixels(DangerzoneConverter):
    # XXX: These functions write page data and metadata to a separate file. For now,
    # they act as an anchor point for Qubes to stream back page data/metadata in
    # real time. In the future, they will be completely replaced by their streaming
    # counterparts. See:
    #
    # https://github.com/freedomofpress/dangerzone/issues/443
    async def write_page_count(self, count: int) -> None:
        pass

    async def write_page_width(self, width: int, filename: str) -> None:
        with open(filename, "w") as f:
            f.write(str(width))

    async def write_page_height(self, height: int, filename: str) -> None:
        with open(filename, "w") as f:
            f.write(str(height))

    async def write_page_data(self, data: bytes, filename: str) -> None:
        with open(filename, "wb") as f:
            f.write(data)

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
            # Commented MIMEs are not used in `file` and don't conform to the rules.
            # Left them for just in case
            # PR: https://github.com/freedomofpress/dangerzone/pull/460
            # "application/haansofthwp": {
            #    "type": "libreoffice",
            #    "libreoffice_ext": "h2orestart.oxt",
            # },
            # "application/vnd.hancom.hwp": {
            #    "type": "libreoffice",
            #    "libreoffice_ext": "h2orestart.oxt",
            # },
            "application/x-hwp": {
                "type": "libreoffice",
                "libreoffice_ext": "h2orestart.oxt",
            },
            # .hwpx
            # "application/haansofthwpx": {
            #    "type": "libreoffice",
            #    "libreoffice_ext": "h2orestart.oxt",
            # },
            # "application/vnd.hancom.hwpx": {
            #    "type": "libreoffice",
            #    "libreoffice_ext": "h2orestart.oxt",
            # },
            "application/x-hwp+zip": {
                "type": "libreoffice",
                "libreoffice_ext": "h2orestart.oxt",
            },
            "application/hwp+zip": {
                "type": "libreoffice",
                "libreoffice_ext": "h2orestart.oxt",
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
        mime_type = self.detect_mime_type("/tmp/input_file")

        # Validate MIME type
        if mime_type not in conversions:
            raise errors.DocFormatUnsupported()

        # Temporary fix for the HWPX format
        # Should be removed after new release of `file' (current release 5.44)
        if mime_type == "application/zip":
            file_type = self.detect_mime_type("/tmp/input_file")
            hwpx_file_type = 'Zip data (MIME type "application/hwp+zip"?)'
            if file_type == hwpx_file_type:
                mime_type = "application/x-hwp+zip"

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
            libreoffice_ext = conversion.get("libreoffice_ext", None)
            # Disable conversion for HWP/HWPX on specific platforms. See:
            #
            #     https://github.com/freedomofpress/dangerzone/issues/494
            #     https://github.com/freedomofpress/dangerzone/issues/498
            if libreoffice_ext == "h2orestart.oxt" and running_on_qubes():
                raise errors.DocFormatUnsupportedHWPQubes()
            if libreoffice_ext:
                await self.install_libreoffice_ext(libreoffice_ext)
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
            await self.run_command(
                args,
                error_message="Conversion to PDF with LibreOffice failed",
                timeout_message=(
                    "Error converting document to PDF, LibreOffice timed out after"
                    f" {timeout} seconds"
                ),
                timeout=timeout,
            )
            pdf_filename = "/tmp/input_file.pdf"
            # XXX: Sometimes, LibreOffice can fail with status code 0. So, we need to
            # always check if the file exists. See:
            #
            #     https://github.com/freedomofpress/dangerzone/issues/494
            if not os.path.exists(pdf_filename):
                raise errors.LibreofficeFailure()
        elif conversion["type"] == "convert":
            self.update_progress("Converting to PDF using GraphicsMagick")
            args = [
                "gm",
                "convert",
                "/tmp/input_file",
                "/tmp/input_file.pdf",
            ]
            await self.run_command(
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
            raise errors.InvalidGMConversion(
                f"Invalid conversion type {conversion['type']} for MIME type {mime_type}"
            )
        self.percentage += 3

        # Obtain number of pages
        self.update_progress("Calculating number of pages")
        stdout, _ = await self.run_command(
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
            raise errors.NoPageCountException()

        if num_pages > errors.MAX_PAGES:
            raise errors.MaxPagesException()

        await self.write_page_count(num_pages)

        # Get a more precise timeout, based on the number of pages
        timeout = self.calculate_timeout(size, num_pages)

        async def pdftoppm_progress_callback(line: bytes) -> None:
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
                    raise errors.PDFtoPPMInvalidHeader()

                # Save the width and height
                dims = f.readline().decode().strip()
                width, height = dims.split()
                await self.write_page_width(int(width), width_filename)
                await self.write_page_height(int(height), height_filename)

                maxval = int(f.readline().decode().strip())
                # Check that the depth is 8
                if maxval != 255:
                    raise errors.PDFtoPPMInvalidDepth()

                data = f.read()

            # Save pixel data
            await self.write_page_data(data, rgb_filename)

            # Delete the ppm file
            os.remove(ppm_filename)

        page_base = "/tmp/page"

        await self.run_command(
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

        final_files = (
            glob.glob("/tmp/page-*.rgb")
            + glob.glob("/tmp/page-*.width")
            + glob.glob("/tmp/page-*.height")
        )

        # XXX: Sanity check to avoid situations like #560.
        if not running_on_qubes() and len(final_files) != 3 * num_pages:
            raise errors.PageCountMismatch()

        # Move converted files into /tmp/dangerzone
        for filename in final_files:
            shutil.move(filename, "/tmp/dangerzone")

        self.update_progress("Converted document to pixels")

    async def install_libreoffice_ext(self, libreoffice_ext: str) -> None:
        self.update_progress(f"Installing LibreOffice extension '{libreoffice_ext}'")
        unzip_args = [
            "unzip",
            "-d",
            f"/usr/lib/libreoffice/share/extensions/{libreoffice_ext}/",
            f"/libreoffice_ext/{libreoffice_ext}",
        ]
        await self.run_command(
            unzip_args,
            error_message="LibreOffice extension installation failed (unzipping)",
            timeout_message="unzipping LibreOffice extension timed out 5 seconds",
            timeout=5,
        )

    def detect_mime_type(self, path: str) -> str:
        """Detect MIME types in a platform-agnostic type.

        Detect the MIME type of a file, either on Qubes or container platforms.
        """
        try:
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file("/tmp/input_file")
        except TypeError:
            mime_type = magic.detect_from_filename("/tmp/input_file").mime_type

        return mime_type


async def main() -> int:
    converter = DocumentToPixels()

    try:
        await converter.convert()
        error_code = 0  # Success!
    except errors.ConversionException as e:  # Expected Errors
        error_code = e.error_code
    except Exception as e:
        converter.update_progress(str(e), error=True)
        error_code = errors.UnexpectedConversionError.error_code
    if not running_on_qubes():
        # Write debug information (containers version)
        with open("/tmp/dangerzone/captured_output.txt", "wb") as container_log:
            container_log.write(converter.captured_output)
    return error_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
