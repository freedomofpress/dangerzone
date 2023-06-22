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

from .common import DangerzoneConverter, running_on_qubes


class PixelsToPDF(DangerzoneConverter):
    async def convert(self) -> None:
        self.percentage = 50.0

        num_pages = len(glob.glob("/tmp/dangerzone/page-*.rgb"))
        total_size = 0.0

        # Convert RGB files to PDF files
        percentage_per_page = 45.0 / num_pages
        for page in range(1, num_pages + 1):
            filename_base = f"/tmp/dangerzone/page-{page}"
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
                await self.run_command(
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
                await self.run_command(
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
                await self.run_command(
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
        await self.run_command(
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
        await self.run_command(
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
        if not running_on_qubes():
            shutil.move("/tmp/safe-output.pdf", "/safezone")
            shutil.move("/tmp/safe-output-compressed.pdf", "/safezone")


async def main() -> int:
    converter = PixelsToPDF()

    try:
        await converter.convert()
    except (RuntimeError, TimeoutError, ValueError) as e:
        converter.update_progress(str(e), error=True)
        return 1
    else:
        return 0  # Success!


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
