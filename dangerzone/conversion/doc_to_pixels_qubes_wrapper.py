import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, TextIO

from .doc_to_pixels import DocumentToPixels


def _read_bytes() -> bytes:
    """Read bytes from the stdin."""
    data = sys.stdin.buffer.read()
    if data is None:
        raise EOFError
    return data


def _write_bytes(data: bytes, file: TextIO = sys.stdout) -> None:
    file.buffer.write(data)


def _write_text(text: str, file: TextIO = sys.stdout) -> None:
    _write_bytes(text.encode(), file=file)


def _write_int(num: int, file: TextIO = sys.stdout) -> None:
    _write_bytes(num.to_bytes(2, signed=False), file=file)


# ==== ASYNC METHODS ====
# We run sync methods in async wrappers, because pure async methods are more difficult:
# https://stackoverflow.com/a/52702646
#
# In practice, because they are I/O bound and we don't have many running concurrently,
# they shouldn't cause a problem.


async def read_bytes() -> bytes:
    return await asyncio.to_thread(_read_bytes)


async def write_bytes(data: bytes, file: TextIO = sys.stdout) -> None:
    return await asyncio.to_thread(_write_bytes, data, file=file)


async def write_text(text: str, file: TextIO = sys.stdout) -> None:
    return await asyncio.to_thread(_write_text, text, file=file)


async def write_int(num: int, file: TextIO = sys.stdout) -> None:
    return await asyncio.to_thread(_write_int, num, file=file)


async def main() -> None:
    out_dir = Path("/tmp/dangerzone")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir()

    try:
        data = await read_bytes()
    except EOFError:
        sys.exit(1)

    with open("/tmp/input_file", "wb") as f:
        f.write(data)

    converter = DocumentToPixels()
    await converter.convert()

    num_pages = len(list(out_dir.glob("*.rgb")))
    await write_int(num_pages)
    for num_page in range(1, num_pages + 1):
        page_base = out_dir / f"page-{num_page}"
        with open(f"{page_base}.width", "r") as width_file:
            width = int(width_file.read())
        with open(f"{page_base}.height", "r") as height_file:
            height = int(height_file.read())
        await write_int(width)
        await write_int(height)
        with open(f"{page_base}.rgb", "rb") as rgb_file:
            rgb_data = rgb_file.read()
            await write_bytes(rgb_data)

    # Write debug information
    await write_bytes(converter.captured_output, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
