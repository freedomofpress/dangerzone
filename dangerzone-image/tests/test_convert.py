import asyncio
import gzip
import io
from pathlib import Path
from typing import List, Tuple

import pytest
from conversion import errors
from conversion.common import INT_BYTES
from conversion.doc_to_pixels import DocumentToPixels

from .conftest import TEST_DOCS_DIRECTORY, for_each_doc

REFERENCE_DIR = Path(__file__).parent / "test_docs" / "reference"
_GZIP_MAGIC = b"\x1f\x8b"


class CapturingDocumentToPixels(DocumentToPixels):
    """DocumentToPixels subclass that captures output to local buffers."""

    def __init__(self) -> None:
        super().__init__()
        self._pixel_output = io.BytesIO()
        self._progress_lines: List[str] = []

    async def write_page_count(self, count: int) -> None:
        self._pixel_output.write(count.to_bytes(INT_BYTES, "big", signed=False))

    async def write_page_width(self, width: int) -> None:
        self._pixel_output.write(width.to_bytes(INT_BYTES, "big", signed=False))

    async def write_page_height(self, height: int) -> None:
        self._pixel_output.write(height.to_bytes(INT_BYTES, "big", signed=False))

    async def write_page_data(self, data: bytes) -> None:
        self._pixel_output.write(bytes(data))

    def update_progress(self, text: str, *, error: bool = False) -> None:
        self._progress_lines.append(text)


def parse_pixel_output(data: bytes) -> List[Tuple[int, int, bytes]]:
    """Parse the binary pixel output into a list of (width, height, rgb_data) per page."""
    offset = 0
    page_count = int.from_bytes(data[offset : offset + INT_BYTES], "big")
    offset += INT_BYTES

    pages = []
    for _ in range(page_count):
        width = int.from_bytes(data[offset : offset + INT_BYTES], "big")
        offset += INT_BYTES
        height = int.from_bytes(data[offset : offset + INT_BYTES], "big")
        offset += INT_BYTES
        size = width * height * 3  # RGB
        rgb_data = data[offset : offset + size]
        offset += size
        pages.append((width, height, rgb_data))

    return pages


def read_reference_data(path: Path) -> bytes:
    data = path.read_bytes()
    if data.startswith(_GZIP_MAGIC):
        return gzip.decompress(data)
    return data


def write_reference_data(path: Path, data: bytes) -> None:
    path.write_bytes(gzip.compress(data))


async def run_local_conversion(doc: Path) -> tuple[bytes, List[str]]:
    input_file = Path("/tmp/input_file")
    try:
        input_file.write_bytes(doc.read_bytes())

        converter = CapturingDocumentToPixels()
        await converter.convert()
        return converter._pixel_output.getvalue(), converter._progress_lines
    finally:
        if input_file.exists():
            input_file.unlink()


async def run_container_conversion(
    doc: Path, container_image: str, container_security_args: List[str]
) -> tuple[int, bytes, bytes]:
    proc = await asyncio.subprocess.create_subprocess_exec(
        "podman",
        "run",
        *container_security_args,
        "--rm",
        "-i",
        container_image,
        "/usr/bin/python3",
        "-m",
        "dangerzone.conversion.doc_to_pixels",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=doc.read_bytes())
    return proc.returncode, stdout, stderr


@for_each_doc
@pytest.mark.asyncio
async def test_convert_document(request: pytest.FixtureRequest, doc: Path) -> None:
    """Test conversion to pixels for each valid document.

    By default, conversion tests run in a container; pass --local to run locally.
    Reference pixel data comparisons are only performed in container mode.
    """
    if request.config.getoption("--local"):
        pixel_data, progress = await run_local_conversion(doc)

        # Check progress messages
        assert "Converted document to pixels" in progress
    else:
        container_image = request.getfixturevalue("container_image")
        container_security_args = request.getfixturevalue("container_security_args")
        returncode, pixel_data, stderr = await run_container_conversion(
            doc, container_image, container_security_args
        )
        assert returncode == 0, (
            f"Container conversion failed (exit {returncode}).\n"
            f"stderr: {stderr.decode(errors='replace')}"
        )

        reference_bin = REFERENCE_DIR / f"{doc.stem}.bin"
        if request.config.getoption("--update-pixel-references"):
            REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
            write_reference_data(reference_bin, pixel_data)
        elif reference_bin.exists():
            assert pixel_data == read_reference_data(reference_bin), (
                f"Pixel data does not match reference for {doc.name}. "
                "Run with --update-pixel-references to regenerate."
            )

    # Parse and validate pixel data structure
    pages = parse_pixel_output(pixel_data)
    assert len(pages) > 0, "Expected at least one page"
    for width, height, rgb_data in pages:
        assert width > 0, "Page width must be positive"
        assert height > 0, "Page height must be positive"
        assert len(rgb_data) == width * height * 3, "RGB data length mismatch"


@pytest.mark.parametrize(
    "bad_doc, expected_error",
    [
        (TEST_DOCS_DIRECTORY / "sample_bad_pdf.pdf", errors.DocFormatUnsupported),
        pytest.param("pdf_11k_pages", errors.MaxPagesException),
    ],
    indirect=["bad_doc"],
)
@pytest.mark.asyncio
async def test_bad_pdf(
    request: pytest.FixtureRequest, bad_doc: Path, expected_error: type
) -> None:
    """Test that invalid documents raise the expected errors."""
    if request.config.getoption("--local"):
        with pytest.raises(expected_error):
            await run_local_conversion(bad_doc)
    else:
        container_image = request.getfixturevalue("container_image")
        container_security_args = request.getfixturevalue("container_security_args")
        returncode, _stdout, stderr = await run_container_conversion(
            bad_doc, container_image, container_security_args
        )
        assert returncode == expected_error.error_code, (
            f"Container conversion failed with exit {returncode} "
            f"(expected {expected_error.error_code}).\n"
            f"stderr: {stderr.decode(errors='replace')}"
        )
