"""
Standalone random fuzzer for the Dangerzone IPC pixel stream protocol.

This is a dependency-free alternative to fuzz_ipc_protocol.py (which uses
Atheris / libFuzzer). It generates random byte strings and feeds them into
the same IPC parsing logic. Not coverage-guided, but good enough for CI
smoke tests or environments where Atheris is unavailable.

The IPC protocol between the container and the host transmits rasterized pages
over stdout as a binary stream:

    page_count: 2 bytes, big-endian unsigned int
    Per page:
        width:  2 bytes, big-endian unsigned int
        height: 2 bytes, big-endian unsigned int
        pixels: width * height * 3 bytes (raw RGB)

Usage:

    python tests/fuzz_ipc_standalone.py                    # default 10000 iterations
    python tests/fuzz_ipc_standalone.py --iterations 50000
    python tests/fuzz_ipc_standalone.py --seed 42          # reproducible run

Any exception that is NOT an expected protocol-violation error is reported as a
potential bug and causes a non-zero exit.
"""

from __future__ import annotations

import argparse
import os
import random
import struct
import sys
import time
from io import BytesIO
from typing import IO, List, Tuple

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
    """Replay host-side IPC parsing against *data*."""
    f = BytesIO(data)

    n_pages = read_int(f)
    if n_pages == 0 or n_pages > MAX_PAGES:
        raise MaxPagesException()

    for _ in range(n_pages):
        width = read_int(f)
        height = read_int(f)

        if not (1 <= width <= MAX_PAGE_WIDTH):
            raise MaxPageWidthException()
        if not (1 <= height <= MAX_PAGE_HEIGHT):
            raise MaxPageHeightException()

        num_pixels = width * height * 3
        read_bytes(f, num_pixels)


# ---------------------------------------------------------------------------
# Input generators -- mix of purely random bytes and semi-valid structures
# to exercise both garbage and near-valid edge cases.
# ---------------------------------------------------------------------------


def gen_random_bytes(rng: random.Random) -> bytes:
    """Fully random blob, 0-200 bytes."""
    length = rng.randint(0, 200)
    return bytes(rng.getrandbits(8) for _ in range(length))


def gen_short_bytes(rng: random.Random) -> bytes:
    """Very short (0-6 bytes) -- tests truncation paths."""
    length = rng.randint(0, 6)
    return bytes(rng.getrandbits(8) for _ in range(length))


def gen_valid_header_bad_body(rng: random.Random) -> bytes:
    """Valid page count + dimensions but truncated pixel data."""
    n_pages = rng.randint(1, 3)
    buf = struct.pack(">H", n_pages)
    for _ in range(n_pages):
        w = rng.randint(1, 50)
        h = rng.randint(1, 50)
        buf += struct.pack(">HH", w, h)
        # Intentionally short pixel data.
        needed = w * h * 3
        actual = rng.randint(0, needed)
        buf += bytes(rng.getrandbits(8) for _ in range(actual))
    return buf


def gen_boundary_values(rng: random.Random) -> bytes:
    """Exercise boundary values for page count, width, height."""
    boundary = rng.choice([0, 1, 9999, 10000, 10001, 65535])
    buf = struct.pack(">H", boundary)
    if 1 <= boundary <= 3:
        for _ in range(boundary):
            w = rng.choice([0, 1, 10000, 10001, 65535])
            h = rng.choice([0, 1, 10000, 10001, 65535])
            buf += struct.pack(">HH", w, h)
            if 1 <= w <= 10000 and 1 <= h <= 10000:
                # Provide exactly the right amount of pixel data (small dims).
                if w * h * 3 <= 1024:
                    buf += bytes(w * h * 3)
                else:
                    # Too large to allocate in fuzzer -- truncate.
                    buf += bytes(rng.randint(0, 64))
    return buf


def gen_single_valid_page(rng: random.Random) -> bytes:
    """One fully valid page with small dimensions."""
    w = rng.randint(1, 10)
    h = rng.randint(1, 10)
    buf = struct.pack(">H", 1)  # 1 page
    buf += struct.pack(">HH", w, h)
    buf += bytes(w * h * 3)
    return buf


def gen_multi_page_valid(rng: random.Random) -> bytes:
    """Multiple valid pages with small dimensions."""
    n = rng.randint(2, 5)
    buf = struct.pack(">H", n)
    for _ in range(n):
        w = rng.randint(1, 8)
        h = rng.randint(1, 8)
        buf += struct.pack(">HH", w, h)
        buf += bytes(w * h * 3)
    return buf


def gen_zero_dimension(rng: random.Random) -> bytes:
    """Valid page count but zero width or height."""
    buf = struct.pack(">H", 1)
    w = rng.choice([0, rng.randint(1, 100)])
    h = rng.choice([0, rng.randint(1, 100)])
    buf += struct.pack(">HH", w, h)
    return buf


GENERATORS = [
    gen_random_bytes,
    gen_short_bytes,
    gen_valid_header_bad_body,
    gen_boundary_values,
    gen_single_valid_page,
    gen_multi_page_valid,
    gen_zero_dimension,
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standalone random fuzzer for the Dangerzone IPC pixel stream protocol."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10_000,
        help="Number of random inputs to test (default: 10000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: random)",
    )
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else int.from_bytes(os.urandom(8), "big")
    rng = random.Random(seed)

    print(f"Fuzzing IPC pixel stream protocol: {args.iterations} iterations, seed={seed}")
    t0 = time.monotonic()

    unexpected_errors: List[Tuple[int, bytes, Exception]] = []

    for i in range(args.iterations):
        gen = rng.choice(GENERATORS)
        data = gen(rng)

        try:
            parse_ipc_stream(data)
        except EXPECTED_EXCEPTIONS:
            pass
        except Exception as exc:
            unexpected_errors.append((i, data, exc))

    elapsed = time.monotonic() - t0
    rate = args.iterations / elapsed if elapsed > 0 else float("inf")

    print(f"Completed {args.iterations} iterations in {elapsed:.2f}s ({rate:.0f} iter/s)")

    if unexpected_errors:
        print(f"\nFOUND {len(unexpected_errors)} UNEXPECTED EXCEPTION(S):")
        for idx, data, exc in unexpected_errors[:10]:  # show first 10
            print(f"  iteration {idx}: {type(exc).__name__}: {exc}")
            print(f"    input ({len(data)} bytes): {data[:80]!r}{'...' if len(data) > 80 else ''}")
        sys.exit(1)
    else:
        print("No unexpected exceptions found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
