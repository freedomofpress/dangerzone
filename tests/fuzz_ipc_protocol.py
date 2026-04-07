"""
Atheris-based coverage-guided fuzzer for the Dangerzone IPC pixel stream protocol.

The IPC protocol between the container and the host transmits rasterized pages
over stdout as a binary stream:

    page_count: 2 bytes, big-endian unsigned int
    Per page:
        width:  2 bytes, big-endian unsigned int
        height: 2 bytes, big-endian unsigned int
        pixels: width * height * 3 bytes (raw RGB)

The host-side parsing lives in dangerzone/isolation_provider/base.py and
enforces bounds from dangerzone/conversion/errors.py:
    MAX_PAGES = 10000, MAX_PAGE_WIDTH = 10000, MAX_PAGE_HEIGHT = 10000

This fuzzer feeds arbitrary bytes into the parsing logic and flags any exception
that is NOT one of the expected protocol-violation errors. Such an exception
would indicate a parsing bug (e.g., an unhandled integer overflow, an unchecked
allocation, or an unexpected crash in downstream code).

Usage (requires atheris + coverage-guided libFuzzer):

    pip install atheris
    python tests/fuzz_ipc_protocol.py

Standalone alternative (no dependencies):

    python tests/fuzz_ipc_standalone.py --iterations 10000
"""

from __future__ import annotations

import sys
from io import BytesIO
from typing import IO

import atheris

# ---------------------------------------------------------------------------
# Inlined parsing functions from dangerzone/isolation_provider/base.py and
# dangerzone/conversion/common.py.  We inline them to avoid importing the
# full dangerzone package (which pulls in PyMuPDF, Qt, etc.) -- the fuzzer
# only needs the wire-protocol parsing and bounds constants.
# ---------------------------------------------------------------------------

INT_BYTES = 2  # from dangerzone.conversion.common

MAX_PAGES = 10_000
MAX_PAGE_WIDTH = 10_000
MAX_PAGE_HEIGHT = 10_000


class ConverterProcException(Exception):
    """Mirrors dangerzone.conversion.errors.ConverterProcException."""


class MaxPagesException(Exception):
    """Mirrors dangerzone.conversion.errors.MaxPagesException."""


class MaxPageWidthException(Exception):
    """Mirrors dangerzone.conversion.errors.MaxPageWidthException."""


class MaxPageHeightException(Exception):
    """Mirrors dangerzone.conversion.errors.MaxPageHeightException."""


# All exceptions we consider "expected" when feeding garbage into the parser.
EXPECTED_EXCEPTIONS = (
    ConverterProcException,
    MaxPagesException,
    MaxPageWidthException,
    MaxPageHeightException,
)


def read_bytes(f: IO[bytes], size: int, exact: bool = True) -> bytes:
    """Read bytes from a file-like object (mirrors base.read_bytes)."""
    buf = f.read(size)
    if exact and len(buf) != size:
        raise ConverterProcException()
    return buf


def read_int(f: IO[bytes]) -> int:
    """Read 2 bytes from a file-like object, and decode them as int (mirrors base.read_int)."""
    untrusted_int = f.read(INT_BYTES)
    if len(untrusted_int) != INT_BYTES:
        raise ConverterProcException()
    return int.from_bytes(untrusted_int, "big", signed=False)


def parse_ipc_stream(data: bytes) -> None:
    """Replay the host-side IPC parsing logic against *data*.

    This mirrors the parsing in IsolationProvider.convert_with_proc() but
    without the subprocess, OCR, or PDF assembly -- just the wire-protocol
    parsing and bounds checking.
    """
    f = BytesIO(data)

    # 1. Read page count (2 bytes).
    n_pages = read_int(f)
    if n_pages == 0 or n_pages > MAX_PAGES:
        raise MaxPagesException()

    # 2. Per-page: width, height, pixel data.
    for _ in range(n_pages):
        width = read_int(f)
        height = read_int(f)

        if not (1 <= width <= MAX_PAGE_WIDTH):
            raise MaxPageWidthException()
        if not (1 <= height <= MAX_PAGE_HEIGHT):
            raise MaxPageHeightException()

        num_pixels = width * height * 3
        read_bytes(f, num_pixels)


def fuzz_one_input(data: bytes) -> None:
    """Atheris entry point -- called once per fuzzed input."""
    try:
        parse_ipc_stream(data)
    except EXPECTED_EXCEPTIONS:
        # Protocol-level rejection -- this is fine.
        pass
    # Any OTHER exception propagates and Atheris treats it as a crash (bug).


def main() -> None:
    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
