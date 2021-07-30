#!/usr/bin/env python3
import sys
import subprocess
import glob
import os

import magic
from PIL import Image


class DangerzoneConverter:
    def __init__(self):
        pass

    def document_to_pixels(self):
        conversions = {
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
            self._print("The document format is not supported")
            return 1

        # Convert input document to PDF
        conversion = conversions[mime_type]
        if conversion["type"] is None:
            pdf_filename = "/tmp/input_file"
        elif conversion["type"] == "libreoffice":
            self._print(f"Converting to PDF using LibreOffice")
            args = [
                "libreoffice",
                "--headless",
                "--convert-to",
                f"pdf:{conversion['libreoffice_output_filter']}",
                "--outdir",
                "/tmp",
                "/tmp/input_file",
            ]
            try:
                p = subprocess.run(args, timeout=60)
            except subprocess.TimeoutExpired:
                self._print(
                    "Error converting document to PDF, LibreOffice timed out after 60 seconds"
                )
                return 1

            if p.returncode != 0:
                self._print(f"Conversion to PDF failed: {p.stdout}")
                return 1
            pdf_filename = "/tmp/input_file.pdf"
        elif conversion["type"] == "convert":
            self._print(f"Converting to PDF using GraphicsMagick")
            args = [
                "gm",
                "convert",
                "/tmp/input_file",
                "/tmp/input_file.pdf",
            ]
            try:
                p = subprocess.run(args, timeout=60)
            except subprocess.TimeoutExpired:
                self._print(
                    "Error converting document to PDF, GraphicsMagick timed out after 60 seconds"
                )
                return 1
            if p.returncode != 0:
                self._print(f"Conversion to PDF failed: {p.stdout}")
                return 1
            pdf_filename = "/tmp/input_file.pdf"
        else:
            self._print("Invalid conversion type")
            return 1

        # Separate PDF into pages
        self._print("")
        self._print(f"Separating document into pages")
        args = ["pdftk", pdf_filename, "burst", "output", "/tmp/page-%d.pdf"]
        try:
            p = subprocess.run(args, timeout=60)
        except subprocess.TimeoutExpired:
            self._print(
                "Error separating document into pages, pdfseparate timed out after 60 seconds"
            )
            return 1
        if p.returncode != 0:
            self._print(f"Separating document into pages failed: {p.stdout}")
            return 1

        page_filenames = glob.glob("/tmp/page-*.pdf")
        self._print(f"Document has {len(page_filenames)} pages")
        self._print("")

        # Convert to RGB pixel data
        for page in range(1, len(page_filenames) + 1):
            pdf_filename = f"/tmp/page-{page}.pdf"
            png_filename = f"/tmp/page-{page}.png"
            rgb_filename = f"/tmp/page-{page}.rgb"
            width_filename = f"/tmp/page-{page}.width"
            height_filename = f"/tmp/page-{page}.height"
            filename_base = f"/tmp/page-{page}"

            self._print(f"Converting page {page} to pixels")

            # Convert to png
            try:
                p = subprocess.run(
                    ["pdftocairo", pdf_filename, "-png", "-singlefile", filename_base],
                    timeout=60,
                )
            except subprocess.TimeoutExpired:
                self._print(
                    "Error converting from PDF to PNG, pdftocairo timed out after 60 seconds"
                )
                return 1
            if p.returncode != 0:
                self._print(f"Conversion from PDF to PNG failed: {p.stdout}")
                return 1

            # Save the width and height
            im = Image.open(png_filename)
            width, height = im.size
            with open(width_filename, "w") as f:
                f.write(str(width))
            with open(height_filename, "w") as f:
                f.write(str(height))

            # Convert to RGB pixels
            try:
                p = subprocess.run(
                    [
                        "gm",
                        "convert",
                        png_filename,
                        "-depth",
                        "8",
                        f"rgb:{rgb_filename}",
                    ],
                    timeout=60,
                )
            except subprocess.TimeoutExpired:
                self._print(
                    "Error converting from PNG to pixels, convert timed out after 60 seconds"
                )
                return 1
            if p.returncode != 0:
                self._print(f"Conversion from PNG to RGB failed: {p.stdout}")
                return 1

            # Delete the png
            os.remove(png_filename)

        return 0

    def pixels_to_pdf(self):
        num_pages = len(glob.glob("/dangerzone/page-*.rgb"))
        self._print(f"Document has {num_pages} pages")

        # Convert RGB files to PDF files
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

            if os.environ.get("OCR") == "1":
                # OCR the document
                self._print(f"Converting page {page} from pixels to searchable PDF")

                args = [
                    "gm",
                    "convert",
                    "-size",
                    f"{width}x{height}",
                    "-depth",
                    "8",
                    f"rgb:{rgb_filename}",
                    f"png:{png_filename}",
                ]
                try:
                    p = subprocess.run(args, timeout=60)
                except subprocess.TimeoutExpired:
                    self._print(
                        "Error converting pixels to PNG, convert timed out after 60 seconds"
                    )
                    return 1
                if p.returncode != 0:
                    self._print(f"Page {page} conversion failed: {p.stdout}")
                    return 1

                args = [
                    "tesseract",
                    png_filename,
                    ocr_filename,
                    "-l",
                    os.environ.get("OCR_LANGUAGE"),
                    "--dpi",
                    "70",
                    "pdf",
                ]
                try:
                    p = subprocess.run(args, timeout=60)
                except subprocess.TimeoutExpired:
                    self._print(
                        "Error converting PNG to searchable PDF, tesseract timed out after 60 seconds"
                    )
                    return 1
                if p.returncode != 0:
                    self._print(f"Page {page} conversion failed: {p.stdout}")
                    return 1

            else:
                # Don't OCR
                self._print(f"Converting page {page} from pixels to PDF")

                args = [
                    "gm",
                    "convert",
                    "-size",
                    f"{width}x{height}",
                    "-depth",
                    "8",
                    f"rgb:{rgb_filename}",
                    f"pdf:{pdf_filename}",
                ]
                try:
                    p = subprocess.run(args, timeout=60)
                except subprocess.TimeoutExpired:
                    self._print(
                        "Error converting RGB to PDF, convert timed out after 60 seconds"
                    )
                    return 1
                if p.returncode != 0:
                    self._print(f"Page {page} conversion failed: {p.stdout}")
                    return 1

        self._print()

        # Merge pages into a single PDF
        self._print(f"Merging {num_pages} pages into a single PDF")
        args = ["pdfunite"]
        for page in range(1, num_pages + 1):
            args.append(f"/tmp/page-{page}.pdf")
        args.append(f"/tmp/safe-output.pdf")
        try:
            p = subprocess.run(args, timeout=60)
        except subprocess.TimeoutExpired:
            self._print(
                "Error merging pages into a single PDF, pdfunite timed out after 60 seconds"
            )
            return 1
        if p.returncode != 0:
            self._print(f"Merge failed: {p.stdout}")
            return 1

        # Compress
        self._print("Compressing PDF")
        compress_timeout = num_pages * 3
        try:
            p = subprocess.run(
                ["ps2pdf", "/tmp/safe-output.pdf", "/tmp/safe-output-compressed.pdf"],
                timeout=compress_timeout,
            )
        except subprocess.TimeoutExpired:
            self._print(
                f"Error compressing PDF, ps2pdf timed out after {compress_timeout} seconds"
            )
            return 1
        if p.returncode != 0:
            self._print(f"Compression failed: {p.stdout}")
            return 1

        return 0

    def _print(self, s=""):
        print(s)
        sys.stdout.flush()


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} [document-to-pixels]|[pixels-to-pdf]")
        return -1

    converter = DangerzoneConverter()

    if sys.argv[1] == "document-to-pixels":
        return converter.document_to_pixels()

    if sys.argv[1] == "pixels-to-pdf":
        return converter.pixels_to_pdf()

    return -1


if __name__ == "__main__":
    sys.exit(main())
