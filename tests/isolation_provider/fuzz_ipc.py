"""Random fuzzer for the Dangerzone IPC pixel-stream protocol.

This exercises **Layer 1** of the doc-to-pixels trust boundary: the Python
byte-stream parser the host uses to read rasterized pages from the sandboxed
container. For **Layer 2** (the ``fitz.Pixmap`` C constructor that consumes
the parser's output) see ``test_pixmap_boundaries.py``. For a specific MuPDF
CVE reproduction see ``test_cve_2026_3308.py``.

The container writes pages to stdout as a binary stream::

    page_count: 2 bytes, big-endian unsigned int
    Per page:
        width:  2 bytes, big-endian unsigned int
        height: 2 bytes, big-endian unsigned int
        pixels: width * height * 3 bytes (raw RGB)

The fuzzer feeds random byte strings into the real parser (``read_int`` /
``read_bytes`` imported from ``dangerzone.isolation_provider.base``) and
encodes valid seed streams with the same ``int.to_bytes(2, "big")`` framing
that ``DangerzoneConverter._write_int`` (and the ``Dummy`` isolation
provider's ``dummy_script``) emits, so the fuzzer and the real container
agree on byte order and framing by construction.

Any exception that is NOT an expected protocol-violation error is reported
as a potential bug and causes a non-zero exit.

Usage::

    make fuzz                                   # default 10000 iterations
    python tests/isolation_provider/fuzz_ipc.py --iterations 50000
    python tests/isolation_provider/fuzz_ipc.py --seed 42  # reproducible

Not coverage-guided. See ``docs/developer/TESTING.md`` for the coverage-guided
alternative (``fuzz_ipc_protocol.py`` / Atheris).
"""

from __future__ import annotations

import argparse
import io
import os
import random
import sys
import time
from typing import List, Tuple

from dangerzone.conversion.common import INT_BYTES
from dangerzone.conversion.errors import (
    MAX_PAGE_HEIGHT,
    MAX_PAGE_WIDTH,
    MAX_PAGES,
    ConverterProcException,
    MaxPageHeightException,
    MaxPagesException,
    MaxPageWidthException,
)
from dangerzone.isolation_provider.base import read_bytes, read_int

EXPECTED_EXCEPTIONS = (
    ConverterProcException,
    MaxPagesException,
    MaxPageWidthException,
    MaxPageHeightException,
)


def _encode_int(num: int) -> bytes:
    """Encode a 2-byte big-endian int the way the container does.

    Mirrors ``DangerzoneConverter._write_int`` but returns bytes instead of
    writing to stdout, so the fuzzer can build streams in memory.
    """
    return num.to_bytes(INT_BYTES, "big", signed=False)


def parse_ipc_stream(data: bytes) -> None:
    """Replay host-side IPC parsing against *data*.

    Uses the real ``read_int``/``read_bytes`` from the isolation provider,
    so this function drifts if — and only if — the real parser drifts.
    """
    f = io.BytesIO(data)

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
    return rng.randbytes(rng.randint(0, 200))


def gen_short_bytes(rng: random.Random) -> bytes:
    """Very short (0-6 bytes) -- tests truncation paths."""
    return rng.randbytes(rng.randint(0, 6))


def gen_valid_header_bad_body(rng: random.Random) -> bytes:
    """Valid page count + dimensions but truncated pixel data."""
    n_pages = rng.randint(1, 3)
    buf = _encode_int(n_pages)
    for _ in range(n_pages):
        w = rng.randint(1, 50)
        h = rng.randint(1, 50)
        buf += _encode_int(w) + _encode_int(h)
        # Intentionally short pixel data.
        needed = w * h * 3
        actual = rng.randint(0, needed)
        buf += rng.randbytes(actual)
    return buf


def gen_boundary_values(rng: random.Random) -> bytes:
    """Exercise boundary values for page count, width, height."""
    boundary = rng.choice([0, 1, 9999, 10000, 10001, 65535])
    buf = _encode_int(boundary)
    if 1 <= boundary <= 3:
        for _ in range(boundary):
            w = rng.choice([0, 1, 10000, 10001, 65535])
            h = rng.choice([0, 1, 10000, 10001, 65535])
            buf += _encode_int(w) + _encode_int(h)
            if 1 <= w <= 10000 and 1 <= h <= 10000:
                # Provide exactly the right amount of pixel data (small dims).
                if w * h * 3 <= 1024:
                    buf += bytes(w * h * 3)
                else:
                    # Too large to allocate in fuzzer -- truncate.
                    buf += bytes(rng.randint(0, 64))
    return buf


def gen_single_valid_page(rng: random.Random) -> bytes:
    """One fully valid page with small dimensions.

    Equivalent to what ``dummy_script`` emits, but with the dimensions
    randomized instead of hardcoded to 9x9.
    """
    w = rng.randint(1, 10)
    h = rng.randint(1, 10)
    buf = _encode_int(1) + _encode_int(w) + _encode_int(h)
    buf += bytes(w * h * 3)
    return buf


def gen_multi_page_valid(rng: random.Random) -> bytes:
    """Multiple valid pages with small dimensions."""
    n = rng.randint(2, 5)
    buf = _encode_int(n)
    for _ in range(n):
        w = rng.randint(1, 8)
        h = rng.randint(1, 8)
        buf += _encode_int(w) + _encode_int(h)
        buf += bytes(w * h * 3)
    return buf


def gen_zero_dimension(rng: random.Random) -> bytes:
    """Valid page count but zero width or height."""
    w = rng.choice([0, rng.randint(1, 100)])
    h = rng.choice([0, rng.randint(1, 100)])
    return _encode_int(1) + _encode_int(w) + _encode_int(h)


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

    print(
        f"Fuzzing IPC pixel stream protocol: {args.iterations} iterations, seed={seed}"
    )
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

    print(
        f"Completed {args.iterations} iterations in {elapsed:.2f}s ({rate:.0f} iter/s)"
    )

    if unexpected_errors:
        print(f"\nFOUND {len(unexpected_errors)} UNEXPECTED EXCEPTION(S):")
        for idx, data, err in unexpected_errors[:10]:  # show first 10
            print(f"  iteration {idx}: {type(err).__name__}: {err}")
            print(
                f"    input ({len(data)} bytes): {data[:80]!r}"
                f"{'...' if len(data) > 80 else ''}"
            )
        sys.exit(1)
    else:
        print("No unexpected exceptions found.")

    # Optional: exercise fitz.Pixmap if PyMuPDF is available
    fuzz_pixmap(rng, iterations=min(args.iterations, 1000))

    sys.exit(0)


# ---------------------------------------------------------------------------
# fitz.Pixmap boundary fuzzer (runs if PyMuPDF is installed)
# ---------------------------------------------------------------------------


def fuzz_pixmap(rng: random.Random, iterations: int = 1000) -> None:
    """Exercise fitz.Pixmap with adversarial dimensions and pixel data.

    This targets the actual C attack surface (MuPDF fz_pixmap) rather than
    the Python IPC protocol parsing above. Runs only if PyMuPDF is available.
    """
    try:
        import fitz
    except ImportError:
        print("\nSkipping fitz.Pixmap fuzzing (PyMuPDF not installed)")
        return

    print(f"\nFuzzing fitz.Pixmap: {iterations} iterations")
    t0 = time.monotonic()

    colorspaces = [fitz.csRGB, fitz.csGRAY, fitz.csCMYK]
    cs_channels = {id(fitz.csRGB): 3, id(fitz.csGRAY): 1, id(fitz.csCMYK): 4}

    boundary_dims = [0, 1, 2, 100, 9999, 10000, 10001, 65535, 33554432, 67108864]
    crashes = 0
    graceful_errors = 0
    successes = 0

    for i in range(iterations):
        cs = rng.choice(colorspaces)
        channels = cs_channels[id(cs)]

        # Mix of targeted boundary values and random dimensions.
        if rng.random() < 0.7:
            w = rng.choice(boundary_dims)
            h = rng.choice(boundary_dims)
        else:
            w = rng.randint(0, 100_000_000)
            h = rng.randint(0, 10)

        # Skip massive allocations that don't wrap (to avoid OOMing the fuzzer),
        # but ALLOW dimensions that might wrap to a small value (which is the bug).
        # w * channels * 2 (16-bit) wrap check:
        potential_stride = (w * 16 * channels + 7) >> 3
        if potential_stride > 50_000_000 and (potential_stride % (2**32)) > 1000:
            h = 1
            if potential_stride > 200_000_000 and (potential_stride % (2**32)) > 1000:
                continue # Skip truly massive non-wrapping ones

        try:
            pix = fitz.Pixmap(cs, fitz.IRect(0, 0, w, h), False)
            successes += 1

            # If we got a pixmap, verify samples length is consistent
            expected = w * h * channels
            actual = len(pix.samples)
            if actual != expected and w > 0 and h > 0:
                print(
                    f"  WARNING: iteration {i}: samples mismatch "
                    f"w={w} h={h} ch={channels} expected={expected} got={actual}"
                )

            pix = None  # release memory
        except (ValueError, RuntimeError, MemoryError, OverflowError):
            graceful_errors += 1
        except Exception as exc:
            # Unexpected exception type - worth investigating
            crashes += 1
            print(
                f"  UNEXPECTED: iteration {i}: {type(exc).__name__}: {exc} "
                f"(w={w}, h={h}, cs_channels={channels})"
            )

    elapsed = time.monotonic() - t0
    rate = iterations / elapsed if elapsed > 0 else float("inf")
    print(
        f"  Completed {iterations} pixmap iterations in {elapsed:.2f}s ({rate:.0f}/s)"
    )
    print(
        f"  Results: {successes} ok, {graceful_errors} rejected, {crashes} unexpected"
    )

    if crashes > 0:
        print(f"  WARNING: {crashes} unexpected exceptions in fitz.Pixmap fuzzing")


if __name__ == "__main__":
    main()
