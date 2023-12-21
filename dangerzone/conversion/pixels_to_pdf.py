#!/usr/bin/env python3
"""
Here are the steps, with progress bar percentages:

- 50%-95%: Convert each page of pixels into a PDF (each page takes 45/n%, where n is the number of pages)
- 95%-100%: Compress the final PDF
"""
import asyncio
import glob
import json
import os
import shutil
import sys
from typing import Optional

from .common import DEFAULT_DPI, DangerzoneConverter, get_tessdata_dir, running_on_qubes


class PixelsToPDF(DangerzoneConverter):
    async def convert(
        self, ocr_lang: Optional[str] = None, tempdir: Optional[str] = None
    ) -> None:
        self.percentage = 50.0
        if tempdir is None:
            tempdir = "/tmp"

        # XXX lazy loading of fitz module to avoid import issues on non-Qubes systems
        import fitz

        num_pages = len(glob.glob(f"{tempdir}/dangerzone/page-*.rgb"))
        total_size = 0.0

        safe_doc = fitz.Document()

        # Convert RGB files to PDF files
        percentage_per_page = 45.0 / num_pages
        for page_num in range(1, num_pages + 1):
            filename_base = f"{tempdir}/dangerzone/page-{page_num}"
            rgb_filename = f"{filename_base}.rgb"
            width_filename = f"{filename_base}.width"
            height_filename = f"{filename_base}.height"

            with open(width_filename) as f:
                width = int(f.read().strip())
            with open(height_filename) as f:
                height = int(f.read().strip())
            with open(rgb_filename, "rb") as rgb_f:
                untrusted_rgb_data = rgb_f.read()
            # The first few operations happen on a per-page basis.
            page_size = len(untrusted_rgb_data)
            total_size += page_size
            timeout = self.calculate_timeout(page_size, 1)
            pixmap = fitz.Pixmap(
                fitz.Colorspace(fitz.CS_RGB), width, height, untrusted_rgb_data, False
            )
            pixmap.set_dpi(DEFAULT_DPI, DEFAULT_DPI)
            if ocr_lang:  # OCR the document
                self.update_progress(
                    f"Converting page {page_num}/{num_pages} from pixels to searchable PDF"
                )
                ocr_pdf_bytes = pixmap.pdfocr_tobytes(
                    compress=True,
                    language=ocr_lang,
                    tessdata=get_tessdata_dir(),
                )
                ocr_pdf = fitz.open("pdf", ocr_pdf_bytes)
                safe_doc.insert_pdf(ocr_pdf)
            else:  # Don't OCR
                self.update_progress(
                    f"Converting page {page_num}/{num_pages} from pixels to PDF"
                )
                safe_doc.insert_file(pixmap)

            self.percentage += percentage_per_page

        # Next operations apply to the all the pages, so we need to recalculate the
        # timeout.
        timeout = self.calculate_timeout(total_size, num_pages)

        self.percentage = 100.0
        self.update_progress("Safe PDF created")

        # Move converted files into /safezone
        if running_on_qubes():
            safe_pdf_path = f"{tempdir}/safe-output-compressed.pdf"
        else:
            safe_pdf_path = f"/safezone/safe-output-compressed.pdf"

        safe_doc.save(safe_pdf_path)


async def main() -> int:
    ocr_lang = os.environ.get("OCR_LANGUAGE") if os.environ.get("OCR") == "1" else None
    converter = PixelsToPDF()

    try:
        await converter.convert(ocr_lang)
        error_code = 0  # Success!

    except (RuntimeError, TimeoutError, ValueError) as e:
        converter.update_progress(str(e), error=True)
        error_code = 1

    if not running_on_qubes():
        # Write debug information (containers version)
        with open("/safezone/captured_output.txt", "wb") as container_log:
            container_log.write(converter.captured_output)
    return error_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
