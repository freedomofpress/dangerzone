import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, TextIO

from . import errors
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


class QubesDocumentToPixels(DocumentToPixels):
    # Override the write_page_* functions to stream data back to the caller, instead of
    # writing it to separate files. This way, we have more accurate progress reports and
    # client-side timeouts. See also:
    #
    # https://github.com/freedomofpress/dangerzone/issues/443
    # https://github.com/freedomofpress/dangerzone/issues/557

    async def write_page_count(self, count: int) -> None:
        return await write_int(count)

    async def write_page_width(self, width: int, filename: str) -> None:
        return await write_int(width)

    async def write_page_height(self, height: int, filename: str) -> None:
        return await write_int(height)

    async def write_page_data(self, data: bytes, filename: str) -> None:
        return await write_bytes(data)


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

    try:
        converter = QubesDocumentToPixels()
        await converter.convert()
    except errors.ConversionException as e:
        await write_bytes(str(e).encode(), file=sys.stderr)
        sys.exit(e.error_code)
    except OSError:
        error_code = errors.ServerOutOfTempSpaceError.error_code
        sys.exit(error_code)
    except Exception as e:
        await write_bytes(str(e).encode(), file=sys.stderr)
        error_code = errors.UnexpectedConversionError.error_code
        sys.exit(error_code)

    # Write debug information
    await write_bytes(converter.captured_output, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
