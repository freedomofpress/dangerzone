import argparse
import asyncio
import os
import secrets
import shutil
import sys
import tarfile
import zipfile
from typing import Dict, List, Optional

try:
    import py7zr
except ImportError:
    py7zr = None

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
            # .eml
            "message/rfc822": {"type": "eml"},
            # .txt
            "text/plain": {"type": "libreoffice"},
            # .html
            "text/html": {"type": "libreoffice"},
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
        elif conversion["type"] == "eml":
            # This should now be handled by extract_recursive/mailbagit during indexing
            # But if somehow we are called directly on an EML in sanitize mode:
            raise errors.DocFormatUnsupported(
                "Email files must be processed via archive mode (indexing)"
            )
        elif conversion["type"] == "libreoffice":
            doc = await self._convert_libreoffice(input_file, conversion)
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

    async def _convert_libreoffice(
        self, input_file: str, conversion: Dict[str, Optional[str]]
    ) -> fitz.Document:
        """Convert a document to PDF using LibreOffice."""
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
        # LibreOffice outputs to /tmp/<basename>.pdf
        base = os.path.basename(input_file)
        # If input_file has no extension, LibreOffice still adds .pdf
        # If it has extension, it replaces it.
        name_part = os.path.splitext(base)[0]
        pdf_filename = os.path.join("/tmp", f"{name_part}.pdf")
        # XXX: Sometimes, LibreOffice can fail with status code 0. So, we need to
        # always check if the file exists. See:
        #
        #     https://github.com/freedomofpress/dangerzone/issues/494
        if not os.path.exists(pdf_filename):
            raise errors.LibreofficeFailure()
        try:
            return fitz.open(pdf_filename)
        except (ValueError, fitz.FileDataError):
            raise errors.DocCorruptedException()

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

SUPPORTED_EMAIL_MIMES = [
    "message/rfc822",
    "application/vnd.ms-outlook",
    "application/mbox",
]


def is_archive(path: str) -> bool:
    try:
        mime_type = magic.from_file(path, mime=True)
    except Exception:
        mime_type = "application/octet-stream"
    return mime_type in SUPPORTED_ARCHIVE_MIMES


def get_email_format(path: str) -> Optional[str]:
    """Identify the email format (eml, msg, mbox) based on mime, description, and content."""
    try:
        mime_type = magic.from_file(path, mime=True)
        description = magic.from_file(path, mime=False).lower()
    except Exception:
        return None

    if mime_type == "application/vnd.ms-outlook" or "outlook" in description:
        return "msg"
    if mime_type == "application/mbox" or "mbox" in description:
        return "mbox"
    if mime_type == "message/rfc822":
        return "eml"

    # Use magic description for robust detection
    if "mime entity" in description or "rfc 822 mail" in description:
        return "eml"

    # Content-based check for ambiguous text/plain files
    if mime_type == "text/plain":
        try:
            from email.parser import BytesHeaderParser
            with open(path, "rb") as f:
                start_bytes = f.read(4096)
                start = start_bytes.lower()
                
                # MBOX heuristic: starts with "From "
                if start.startswith(b"from "):
                    return "mbox"
                
                # EML heuristic: multiple standard headers
                msg = BytesHeaderParser().parsebytes(start_bytes)
                headers = ["subject", "from", "to", "date", "mime-version"]
                found_count = 0
                for h in headers:
                    if h in msg:
                        found_count += 1
                if found_count >= 2:
                    return "eml"
        except Exception:
            pass

    return None


def is_email(path: str) -> bool:
    return get_email_format(path) is not None


async def _extract_email(input_path: str, output_dir: str, converter: "DocumentToPixels") -> None:
    """Extract email body and attachments using mailbagit."""
    temp_mailbag_out = f"{output_dir}_mailbag_tmp"

    input_format = get_email_format(input_path) or "eml"

    args = [
        "mailbagit",
        input_path,
        "--mailbag",
        temp_mailbag_out,
        "--input",
        input_format,
        "--derivatives",
        "html",
    ]

    await converter.run_command(
        args,
        error_message="mailbagit conversion failed",
    )

    # Move relevant items to output_dir
    for root, dirs, files in os.walk(temp_mailbag_out):
        if "attachments" in dirs:
            src_attachments = os.path.join(root, "attachments")
            dest_attachments = os.path.join(output_dir, "attachments")
            os.makedirs(dest_attachments, exist_ok=True)
            for item in os.listdir(src_attachments):
                shutil.move(os.path.join(src_attachments, item), os.path.join(dest_attachments, item))
            # Don't walk into the moved directory
            dirs.remove("attachments")
        
        for f in files:
            if f.lower().endswith(".html"):
                shutil.move(os.path.join(root, f), os.path.join(output_dir, "body.html"))

    shutil.rmtree(temp_mailbag_out)

    # Final cleanup of output_dir to ensure no metadata files leaked through
    metadata_names = ["attachments.csv", "mailbag.csv", "bag-info.txt", "bagit.txt", "mailbag.log"]
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            f_lower = f.lower()
            if f_lower in metadata_names or f_lower.startswith("manifest-") or f_lower.startswith("tagmanifest-"):
                os.remove(os.path.join(root, f))



async def _extract_recursive_all(
    input_path: str,
    output_dir: str,
    max_files: int,
    counter: List[int],
    converter: "DocumentToPixels",
) -> None:
    """Helper to recursively extract archives AND emails to a directory."""
    if counter[0] >= max_files:
        return

    if zipfile.is_zipfile(input_path):
        with zipfile.ZipFile(input_path, "r") as z:
            z.extractall(output_dir)
    elif py7zr and py7zr.is_7zfile(input_path):
        with py7zr.SevenZipFile(input_path, mode="r") as z:
            z.extractall(output_dir)
    elif tarfile.is_tarfile(input_path):
        with tarfile.open(input_path, "r:*") as t:
            t.extractall(output_dir)
    elif is_email(input_path):
        await _extract_email(input_path, output_dir, converter)
    else:
        # Check if it's a lone compressed file
        mime = magic.from_file(input_path, mime=True)
        if mime in ["application/gzip", "application/x-bzip2", "application/x-xz"]:
            base = os.path.basename(input_path)
            out_name = os.path.splitext(base)[0]
            import bz2
            import gzip
            import lzma

            if mime == "application/gzip":
                open_func = gzip.open
            elif mime == "application/x-bzip2":
                open_func = bz2.open
            else:
                open_func = lzma.open

            with open_func(input_path, "rb") as f_in:
                with open(os.path.join(output_dir, out_name), "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            return

    # Collect items just extracted to recurse if needed
    items_to_recurse = []
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            items_to_recurse.append(os.path.join(root, file))

    for file_path in items_to_recurse:
        if counter[0] >= max_files:
            return
        if is_archive(file_path) or is_email(file_path):
            sub_out = os.path.join(
                os.path.dirname(file_path), f"{os.path.basename(file_path)}.extracted"
            )
            os.makedirs(sub_out, exist_ok=True)
            await _extract_recursive_all(
                file_path, sub_out, max_files, counter, converter
            )
            counter[0] += 1


async def extract_recursive(
    input_path: str, output_dir: str, converter: "DocumentToPixels"
) -> List[str]:
    """Recursively extract archives and emails."""
    max_files = 1000
    counter = [0]
    await _extract_recursive_all(input_path, output_dir, max_files, counter, converter)
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

    random_id = secrets.token_hex(4)
    temp_input = f"/tmp/dz-input-{random_id}"
    with open(temp_input, "wb") as f:
        f.write(data)

    converter = DocumentToPixels()
    exit_code = 0
    try:
        if is_archive(temp_input) or is_email(temp_input):
            if output_dir is None:
                output_dir = f"/tmp/dz-extracted-{random_id}"
            os.makedirs(output_dir, exist_ok=True)
            files = await extract_recursive(temp_input, output_dir, converter)
            await DocumentToPixels.write_int(len(files))
            for f in files:
                # Protocol: ALWAYS absolute paths for indexed files (start with /)
                path = os.path.abspath(f)
                f_bytes = path.encode()
                await DocumentToPixels.write_int(len(f_bytes))
                await DocumentToPixels.write_bytes(f_bytes)

        else:
            # It's a single file. Protocol: report 1 file, name does NOT start with /
            # We report it as 'tmp/dz-input-xxxx'
            await DocumentToPixels.write_int(1)
            f_bytes = temp_input.lstrip("/").encode()
            await DocumentToPixels.write_int(len(f_bytes))
            await DocumentToPixels.write_bytes(f_bytes)
    except Exception as e:
        await DocumentToPixels.write_bytes(str(e).encode(), file=sys.stderr)
        exit_code = 1

    # Write debug information
    await DocumentToPixels.write_bytes(converter.captured_output, file=sys.stderr)
    if exit_code != 0:
        sys.exit(exit_code)


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

    exit_code = 0
    converter = DocumentToPixels()
    try:
        await converter.convert(input_file)
    except errors.ConversionException as e:
        await DocumentToPixels.write_bytes(str(e).encode(), file=sys.stderr)
        exit_code = e.error_code
    except Exception as e:
        await DocumentToPixels.write_bytes(str(e).encode(), file=sys.stderr)
        exit_code = errors.UnexpectedConversionError.error_code

    # Write debug information
    await DocumentToPixels.write_bytes(converter.captured_output, file=sys.stderr)
    if exit_code != 0:
        sys.exit(exit_code)


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
