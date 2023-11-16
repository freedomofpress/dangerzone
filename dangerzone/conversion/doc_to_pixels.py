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

import fitz
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
        doc = fitz.open(pdf_filename)
        if doc.page_count > errors.MAX_PAGES:
            raise errors.MaxPagesException()
        await self.write_page_count(doc.page_count)

        percentage_per_page = 45.0 / doc.page_count
        page_base = "/tmp/page"
        for page in doc.pages():
            # TODO check if page.number is doc-controlled
            page_num = page.number + 1  # pages start in 1
            rgb_filename = f"{page_base}-{page_num}.rgb"
            width_filename = f"{page_base}-{page_num}.width"
            height_filename = f"{page_base}-{page_num}.height"

            self.percentage += percentage_per_page
            self.update_progress(
                f"Converting page {page_num}/{doc.page_count} to pixels"
            )
            pix = page.get_pixmap(dpi=150)
            rgb_buf = pix.samples_mv
            await self.write_page_width(pix.width, width_filename)
            await self.write_page_height(pix.height, height_filename)
            await self.write_page_data(rgb_buf, rgb_filename)

        final_files = (
            glob.glob("/tmp/page-*.rgb")
            + glob.glob("/tmp/page-*.width")
            + glob.glob("/tmp/page-*.height")
        )

        # XXX: Sanity check to avoid situations like #560.
        if not running_on_qubes() and len(final_files) != 3 * doc.page_count:
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
