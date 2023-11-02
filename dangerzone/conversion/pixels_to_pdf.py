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

from .common import (
    DangerzoneConverter,
    batch_iterator,
    get_batch_timeout,
    running_on_qubes,
)


class PixelsToPDF(DangerzoneConverter):
    async def convert(
        self, ocr_lang: Optional[str] = None, tempdir: Optional[str] = "/tmp"
    ) -> None:
        self.percentage = 50.0

        num_pages = len(glob.glob(f"{tempdir}/page-*.png"))
        total_size = 0.0

        # Convert RGB files to PDF files
        percentage_per_page = 45.0 / num_pages
        for page in range(1, num_pages + 1):
            filename_base = f"{tempdir}/page-{page}"
            png_filename = f"{filename_base}.png"
            pdf_filename = f"{filename_base}.pdf"

            # The first few operations happen on a per-page basis.
            page_size = os.path.getsize(png_filename) / 1024**2
            total_size += page_size
            timeout = self.calculate_timeout(page_size, 1)

            if ocr_lang:  # OCR the document
                self.update_progress(
                    f"Converting page {page}/{num_pages} from pixels to searchable PDF"
                )
                await self.run_command(
                    [
                        "tesseract",
                        png_filename,
                        filename_base,
                        "-l",
                        ocr_lang,
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
                await self.run_command(
                    [
                        "gm",
                        "convert",
                        f"png:{png_filename}",
                        f"pdf:{pdf_filename}",
                    ],
                    error_message=f"Page {page}/{num_pages} conversion to PDF failed",
                    timeout_message=(
                        "Error converting RGB to PDF, convert timed out after"
                        f" {timeout} seconds"
                    ),
                    timeout=timeout,
                )

            # remove PNG file when it is no longer needed
            os.remove(png_filename)

            self.percentage += percentage_per_page

        # Next operations apply to the all the pages, so we need to recalculate the
        # timeout.
        timeout = self.calculate_timeout(total_size, num_pages)

        # Merge pages into a single PDF
        timeout_per_batch = get_batch_timeout(timeout, num_pages)
        self.update_progress(f"Merging {num_pages} pages into a single PDF")
        for first_page, last_page in batch_iterator(num_pages):
            args = ["pdfunite"]
            accumulator = f"{tempdir}/safe-output.pdf"  # PDF which accumulates pages
            accumulator_temp = f"{tempdir}/safe-output_tmp.pdf"
            if first_page > 1:  # Append at the beginning
                args.append(accumulator)
            for page in range(first_page, last_page + 1):
                args.append(f"{tempdir}/page-{page}.pdf")
            args.append(accumulator_temp)
            await self.run_command(
                args,
                error_message="Merging pages into a single PDF failed",
                timeout_message=(
                    "Error merging pages into a single PDF, pdfunite timed out after"
                    f" {timeout_per_batch} seconds"
                ),
                timeout=timeout_per_batch,
            )
            for page in range(first_page, last_page + 1):
                os.remove(f"{tempdir}/page-{page}.pdf")
            os.rename(accumulator_temp, accumulator)

        self.percentage += 2

        # Compress
        self.update_progress("Compressing PDF")
        await self.run_command(
            [
                "ps2pdf",
                f"{tempdir}/safe-output.pdf",
                f"{tempdir}/safe-output-compressed.pdf",
            ],
            error_message="Compressing PDF failed",
            timeout_message=(
                f"Error compressing PDF, ps2pdf timed out after {timeout} seconds"
            ),
            timeout=timeout,
        )

        self.percentage = 100.0
        self.update_progress("Safe PDF created")

        # Move converted files into /safezone
        if not running_on_qubes():
            shutil.move(f"{tempdir}/safe-output.pdf", "/safezone")
            shutil.move(f"{tempdir}/safe-output-compressed.pdf", "/safezone")


async def main() -> int:
    ocr_lang = os.environ.get("OCR_LANGUAGE") if os.environ.get("OCR") == "1" else None
    converter = PixelsToPDF()

    try:
        await converter.convert(ocr_lang, tempdir="/tmp/dangerzone")
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
