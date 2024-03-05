#!/usr/bin/env python3
"""
Here are the steps, with progress bar percentages:

- 50%-95%: Convert each page of pixels into a PDF (each page takes 45/n%, where n is the number of pages)
- 95%-100%: Compress the final PDF
"""
import asyncio
import contextlib
import glob
import io
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
            tempdir = "/safezone"

        # XXX lazy loading of fitz module to avoid import issues on non-Qubes systems
        import fitz

        num_pages = len(glob.glob(f"{tempdir}/pixels/page-*.rgb"))
        total_size = 0.0

        safe_doc = fitz.Document()

        # Convert RGB files to PDF files
        percentage_per_page = 45.0 / num_pages
        for page_num in range(1, num_pages + 1):
            filename_base = f"{tempdir}/pixels/page-{page_num}"
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
            with contextlib.redirect_stdout(io.StringIO()):
                pixmap = fitz.Pixmap(
                    fitz.Colorspace(fitz.CS_RGB),
                    width,
                    height,
                    untrusted_rgb_data,
                    False,
                )
            pixmap.set_dpi(DEFAULT_DPI, DEFAULT_DPI)
            if ocr_lang:  # OCR the document
                self.update_progress(
                    f"Converting page {page_num}/{num_pages} from pixels to searchable PDF"
                )
                if int(fitz.version[2]) >= 20230621000001:
                    page_pdf_bytes = pixmap.pdfocr_tobytes(
                        compress=True,
                        language=ocr_lang,
                        tessdata=get_tessdata_dir(),
                    )
                else:
                    # XXX: In PyMuPDF v1.22.5, the function signature of
                    # `pdfocr_tobytes()` / `pdfocr_save()` was extended with an argument
                    # to explicitly set the Tesseract data dir [1].
                    #
                    # In earlier versions, the PyMuPDF developers recommend setting this
                    # path via the TESSDATA_PREFIX environment variable. In practice,
                    # this environment variable is read at import time, so subsequent
                    # changes to the environment variable are not tracked [2].
                    #
                    # To make things worse, any attempt to alter the internal attribute
                    # (`fitz.TESSDATA_PREFIX`) makes no difference as well, when using
                    # the OCR functions. That's due to the way imports work in `fitz`,
                    # where somehow the internal `fitz.fitz` module is shadowed.
                    #
                    # A hacky solution is to grab the `fitz.fitz` module from
                    # `sys.modules`, and set there the TESSDATA_PREFIX variable. We can
                    # get away with this hack because we have a proper solution for
                    # subsequent PyMuPDF versions, and we know that nothing will change
                    # in older versions.
                    #
                    # TODO: Remove after oldest distro has PyMuPDF >= v1.22.5
                    #
                    # [1]: https://pymupdf.readthedocs.io/en/latest/pixmap.html#Pixmap.pdfocr_save
                    # [2]: https://github.com/pymupdf/PyMuPDF/blob/0368e56cfa6afb55bcf6c726e7f51a2a16a5ccba/fitz/fitz.i#L308
                    sys.modules["fitz.fitz"].TESSDATA_PREFIX = get_tessdata_dir()  # type: ignore [attr-defined]

                    page_pdf_bytes = pixmap.pdfocr_tobytes(
                        compress=True,
                        language=ocr_lang,
                    )
                ocr_pdf = fitz.open("pdf", page_pdf_bytes)
            else:  # Don't OCR
                self.update_progress(
                    f"Converting page {page_num}/{num_pages} from pixels to PDF"
                )
                page_doc = fitz.Document()
                page_doc.insert_file(pixmap)
                page_pdf_bytes = page_doc.tobytes(deflate_images=True)

            safe_doc.insert_pdf(fitz.open("pdf", page_pdf_bytes))
            self.percentage += percentage_per_page

        self.percentage = 100.0
        self.update_progress("Safe PDF created")

        # Move converted files into /safezone
        if running_on_qubes():
            safe_pdf_path = f"{tempdir}/safe-output-compressed.pdf"
        else:
            safe_pdf_path = f"/safezone/safe-output-compressed.pdf"

        safe_doc.save(safe_pdf_path, deflate_images=True)

    def update_progress(self, text: str, *, error: bool = False) -> None:
        if running_on_qubes():
            if self.progress_callback:
                self.progress_callback(error, text, self.percentage)
        else:
            print(
                json.dumps(
                    {"error": error, "text": text, "percentage": self.percentage}
                )
            )
            sys.stdout.flush()


async def main() -> int:
    ocr_lang = os.environ.get("OCR_LANGUAGE") if os.environ.get("OCR") == "1" else None
    converter = PixelsToPDF()

    try:
        await converter.convert(ocr_lang)
        return 0
    except (RuntimeError, ValueError) as e:
        converter.update_progress(str(e), error=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
