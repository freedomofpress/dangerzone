import argparse
import asyncio
import os
import secrets
import shutil
import sys
import tarfile
import zipfile
from typing import Dict, List, Optional

# XXX: PyMUPDF logs to stdout by default [1]. The PyMuPDF devs provide a way [2] to log to
# stderr, but it's based on environment variables. These envvars are consulted at import
# time [3], so we have to set them here, before we import `fitz`.
#
# [1] https://github.com/freedomofpress/dangerzone/issues/877
# [2] https://github.com/pymupdf/PyMuPDF/issues/3135#issuecomment-1992625724
# [3] https://github.com/pymupdf/PyMuPDF/blob/9717935eeb2d50d15440d62575878214226795f9/src/__init__.py#L62-L63
os.environ["PYMUPDF_MESSAGE"] = "fd:2"
os.environ["PYMUPDF_LOG"] = "fd:2"


import fitz
import magic

from . import errors
from .common import DEFAULT_DPI, DangerzoneConverter, running_on_qubes


class DocumentToPixels(DangerzoneConverter):
    async def write_page_count(self, count: int) -> None:
        return await self.write_int(count)

    async def write_page_width(self, width: int) -> None:
        return await self.write_int(width)

    async def write_page_height(self, height: int) -> None:
        return await self.write_int(height)

    async def write_page_data(self, data: bytes) -> None:
        return await self.write_bytes(data)

    def update_progress(self, text: str, *, error: bool = False) -> None:
        print(text, file=sys.stderr)

    async def convert(self, input_file: str = "/tmp/input_file") -> None:
        conversions: Dict[str, Dict[str, Optional[str]]] = {
            # .pdf
            "application/pdf": {"type": "PyMuPDF"},
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
            # .epub
            "application/epub+zip": {"type": "PyMuPDF"},
            # .svg
            "image/svg+xml": {"type": "PyMuPDF"},
            # .bmp
            "image/bmp": {"type": "PyMuPDF"},
            # .pnm
            "image/x-portable-anymap": {"type": "PyMuPDF"},
            # .pbm
            "image/x-portable-bitmap": {"type": "PyMuPDF"},
            # .ppm
            "image/x-portable-pixmap": {"type": "PyMuPDF"},
            # .jpg
            "image/jpeg": {"type": "PyMuPDF"},
            # .gif
            "image/gif": {"type": "PyMuPDF"},
            # .png
            "image/png": {"type": "PyMuPDF"},
            # .tif
            "image/tiff": {"type": "PyMuPDF"},
            "image/x-tiff": {"type": "PyMuPDF"},
        }

        # Detect MIME type
        mime_type = self.detect_mime_type(input_file)

        # Validate MIME type
        if mime_type not in conversions:
            raise errors.DocFormatUnsupported()

        # Convert input document to PDF
        conversion = conversions[mime_type]
        if conversion["type"] == "PyMuPDF":
            try:
                doc = fitz.open(input_file, filetype=mime_type)
            except (ValueError, fitz.FileDataError):
                raise errors.DocCorruptedException()
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
                input_file,
            ]
            await self.run_command(
                args,
                error_message="Conversion to PDF with LibreOffice failed",
            )
            pdf_filename = f"{input_file}.pdf"
            # XXX: Sometimes, LibreOffice can fail with status code 0. So, we need to
            # always check if the file exists. See:
            #
            #     https://github.com/freedomofpress/dangerzone/issues/494
            if not os.path.exists(pdf_filename):
                raise errors.LibreofficeFailure()
            try:
                doc = fitz.open(pdf_filename)
            except (ValueError, fitz.FileDataError):
                raise errors.DocCorruptedException()
        else:
            # NOTE: This should never be reached
            raise errors.DocFormatUnsupported()

        # Obtain number of pages
        if doc.page_count > errors.MAX_PAGES:
            raise errors.MaxPagesException()
        await self.write_page_count(doc.page_count)

        for page in doc.pages():
            # TODO check if page.number is doc-controlled
            page_num = page.number + 1  # pages start in 1

            self.update_progress(
                f"Converting page {page_num}/{doc.page_count} to pixels"
            )
            pix = page.get_pixmap(dpi=DEFAULT_DPI)
            rgb_buf = pix.samples_mv
            await self.write_page_width(pix.width)
            await self.write_page_height(pix.height)
            await self.write_page_data(rgb_buf)

        self.update_progress("Converted document to pixels")

    async def install_libreoffice_ext(self, libreoffice_ext: str) -> None:
        self.update_progress(f"Installing LibreOffice extension '{libreoffice_ext}'")
        unzip_args = [
            "unzip",
            "-d",
            f"/usr/lib/libreoffice/share/extensions/{libreoffice_ext}/",
            f"/opt/libreoffice_ext/{libreoffice_ext}",
        ]
        await self.run_command(
            unzip_args,
            error_message="LibreOffice extension installation failed (unzipping)",
        )

    def detect_mime_type(self, path: str) -> str:
        """Detect MIME types in a platform-agnostic type.

        Detect the MIME type of a file, either on Qubes or container platforms.
        """
        try:
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file(path)
        except TypeError:
            mime_type = magic.detect_from_filename(path).mime_type

        return mime_type


SUPPORTED_ARCHIVE_MIMES = [
    "application/zip",
    "application/x-tar",
    "application/gzip",
    "application/x-bzip2",
    "application/x-7z-compressed",
    "application/x-xz",
]


def is_archive(path: str) -> bool:
    try:
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(path)
    except TypeError:
        mime_type = magic.detect_from_filename(path).mime_type
    return mime_type in SUPPORTED_ARCHIVE_MIMES


def _extract_to_dir(current_path: str, current_out: str, max_files: int, counter: List[int]) -> None:
    """Helper to recursively extract archives to a directory."""
    if counter[0] >= max_files:
        return

    if zipfile.is_zipfile(current_path):
        with zipfile.ZipFile(current_path, "r") as z:
            z.extractall(current_out)
    elif tarfile.is_tarfile(current_path):
        with tarfile.open(current_path, "r:*") as t:
            t.extractall(current_out)
    else:
        return

    # Check for nested archives and update counter
    for root, dirs, files in os.walk(current_out):
        for file in files:
            if counter[0] >= max_files:
                return
            file_path = os.path.join(root, file)
            counter[0] += 1
            if is_archive(file_path):
                # Extract to a subfolder
                sub_out = os.path.join(root, f"{file}.extracted")
                os.makedirs(sub_out, exist_ok=True)
                _extract_to_dir(file_path, sub_out, max_files, counter)


def extract_recursive(input_path: str, output_dir: str) -> List[str]:
    """Recursively extract archives."""
    max_files = 1000  # Basic protection
    counter = [0]  # Use a list to have a mutable counter across recursion

    _extract_to_dir(input_path, output_dir, max_files, counter)

    # Collect all files that are not directories
    extracted_files = []
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            extracted_files.append(os.path.join(root, file))

    return extracted_files


async def handle_index(output_dir: Optional[str] = None) -> None:
    """Handle the 'index' command: extract archives or move a single file."""
    try:
        data = await DocumentToPixels.read_bytes()
    except EOFError:
        sys.exit(1)

    temp_input = "/tmp/index_input"
    with open(temp_input, "wb") as f:
        f.write(data)

    if output_dir is None:
        output_dir = f"/tmp/dz-extracted-{secrets.token_hex(4)}"

    if is_archive(temp_input):
        os.makedirs(output_dir, exist_ok=True)
        files = extract_recursive(temp_input, output_dir)
        await DocumentToPixels.write_int(len(files))
        for f in files:
            f_bytes = f.encode()
            await DocumentToPixels.write_int(len(f_bytes))
            await DocumentToPixels.write_bytes(f_bytes)
    else:
        # It's a single file
        # If output_dir doesn't exist, we'll use it as the filename
        parent = os.path.dirname(output_dir)
        if parent:
            os.makedirs(parent, exist_ok=True)
        shutil.move(temp_input, output_dir)
        await DocumentToPixels.write_int(1)
        f_bytes = output_dir.encode()
        await DocumentToPixels.write_int(len(f_bytes))
        await DocumentToPixels.write_bytes(f_bytes)


async def handle_sanitize(input_file: Optional[str] = None) -> None:
    """Handle the 'sanitize' command or default behavior: convert a file to pixels."""
    if input_file is None:
        # Backwards compatibility: read from stdin
        try:
            data = await DocumentToPixels.read_bytes()
        except EOFError:
            sys.exit(1)

        input_file = "/tmp/input_file"
        with open(input_file, "wb") as f:
            f.write(data)

    try:
        converter = DocumentToPixels()
        await converter.convert(input_file)
    except errors.ConversionException as e:
        await DocumentToPixels.write_bytes(str(e).encode(), file=sys.stderr)
        sys.exit(e.error_code)
    except Exception as e:
        await DocumentToPixels.write_bytes(str(e).encode(), file=sys.stderr)
        error_code = errors.UnexpectedConversionError.error_code
        sys.exit(error_code)

    # Write debug information
    await DocumentToPixels.write_bytes(converter.captured_output, file=sys.stderr)


async def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--output-dir", default=None)

    sanitize_parser = subparsers.add_parser("sanitize")
    sanitize_parser.add_argument("path", nargs="?", default=None)

    args = parser.parse_args()

    if args.command == "index":
        await handle_index(args.output_dir)
    elif args.command == "sanitize":
        await handle_sanitize(args.path)
    else:
        # Default behavior (backwards compatibility)
        await handle_sanitize()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
