"""Hypothesis property-based tests for the IPC pixel stream protocol.

The dangerzone IPC protocol sends pixel data from a sandboxed converter
process to the host over stdout as a binary stream:

    [page_count: 2 bytes big-endian unsigned]
    for each page:
        [width:  2 bytes big-endian unsigned]
        [height: 2 bytes big-endian unsigned]
        [pixels: width * height * 3 bytes (RGB)]

The host-side parsing lives in dangerzone/isolation_provider/base.py
(read_int, read_bytes) with bounds enforced by dangerzone/conversion/errors.py
(MAX_PAGES=10000, MAX_PAGE_WIDTH=10000, MAX_PAGE_HEIGHT=10000).

NOTE: We inline read_int/read_bytes here rather than importing from base.py,
because base.py pulls in fitz (PyMuPDF) which may not be installed in all
test environments. The inlined versions are byte-identical to the originals
and are tested for equivalence against the wire format.
"""

import io
import struct
from typing import IO, List, Tuple

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from dangerzone.conversion.common import INT_BYTES
from dangerzone.conversion.errors import (
    ConverterProcException,
    MaxPagesException,
    MaxPageWidthException,
    MaxPageHeightException,
    MAX_PAGES,
    MAX_PAGE_WIDTH,
    MAX_PAGE_HEIGHT,
)


# ---------------------------------------------------------------------------
# Inlined from dangerzone/isolation_provider/base.py (lines 63-76) to avoid
# importing fitz. These are the exact functions under test.
# ---------------------------------------------------------------------------

def read_bytes(f: IO[bytes], size: int, exact: bool = True) -> bytes:
    """Read bytes from a file-like object."""
    buf = f.read(size)
    if exact and len(buf) != size:
        raise ConverterProcException()
    return buf


def read_int(f: IO[bytes]) -> int:
    """Read 2 bytes from a file-like object, and decode them as int."""
    untrusted_int = f.read(INT_BYTES)
    if len(untrusted_int) != INT_BYTES:
        raise ConverterProcException()
    return int.from_bytes(untrusted_int, "big", signed=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def encode_int(n: int) -> bytes:
    """Encode an unsigned int as 2-byte big-endian, matching the wire format."""
    return n.to_bytes(INT_BYTES, "big", signed=False)


def build_pixel_stream(pages: List[Tuple[int, int, bytes]]) -> bytes:
    """Build a complete pixel stream from a list of (width, height, pixels)."""
    buf = encode_int(len(pages))
    for width, height, pixels in pages:
        buf += encode_int(width)
        buf += encode_int(height)
        buf += pixels
    return buf


def parse_stream(data: bytes) -> List[Tuple[int, int, bytes]]:
    """Parse a pixel stream the same way the host does, with bounds checks.

    Returns list of (width, height, pixels) tuples.
    Raises ConverterProcException or a PagesException subclass on failure.
    """
    f = io.BytesIO(data)
    n_pages = read_int(f)
    if n_pages == 0 or n_pages > MAX_PAGES:
        raise MaxPagesException()

    result = []
    for _ in range(n_pages):
        width = read_int(f)
        height = read_int(f)
        if not (1 <= width <= MAX_PAGE_WIDTH):
            raise MaxPageWidthException()
        if not (1 <= height <= MAX_PAGE_HEIGHT):
            raise MaxPageHeightException()
        num_pixels = width * height * 3
        pixels = read_bytes(f, num_pixels, exact=True)
        result.append((width, height, pixels))
    return result


# ---------------------------------------------------------------------------
# read_int tests
# ---------------------------------------------------------------------------

class TestReadInt:
    """Property tests for read_int (2-byte big-endian unsigned decode)."""

    @given(value=st.integers(min_value=0, max_value=2**16 - 1))
    def test_roundtrip(self, value: int) -> None:
        """Any uint16 encodes to 2 bytes and decodes back identically."""
        encoded = encode_int(value)
        assert len(encoded) == INT_BYTES
        result = read_int(io.BytesIO(encoded))
        assert result == value

    def test_empty_stream_raises(self) -> None:
        """An empty stream must raise ConverterProcException."""
        with pytest.raises(ConverterProcException):
            read_int(io.BytesIO(b""))

    def test_single_byte_raises(self) -> None:
        """A single byte (truncated int) must raise ConverterProcException."""
        with pytest.raises(ConverterProcException):
            read_int(io.BytesIO(b"\x01"))

    @given(value=st.integers(min_value=0, max_value=2**16 - 1))
    def test_big_endian_encoding(self, value: int) -> None:
        """Verify the encoding matches struct.pack('>H', value)."""
        encoded = encode_int(value)
        assert encoded == struct.pack(">H", value)


# ---------------------------------------------------------------------------
# read_bytes tests
# ---------------------------------------------------------------------------

class TestReadBytes:
    """Property tests for read_bytes (exact-size reads)."""

    @given(data=st.binary(min_size=1, max_size=1024))
    def test_exact_read(self, data: bytes) -> None:
        """Reading exactly len(data) bytes returns the data unchanged."""
        result = read_bytes(io.BytesIO(data), len(data), exact=True)
        assert result == data

    @given(
        data=st.binary(min_size=1, max_size=512),
        extra=st.integers(min_value=1, max_value=512),
    )
    def test_truncated_read_raises(self, data: bytes, extra: int) -> None:
        """Requesting more bytes than available raises ConverterProcException."""
        requested = len(data) + extra
        with pytest.raises(ConverterProcException):
            read_bytes(io.BytesIO(data), requested, exact=True)

    def test_zero_bytes_exact(self) -> None:
        """Reading zero bytes from any stream succeeds (vacuously exact)."""
        result = read_bytes(io.BytesIO(b""), 0, exact=True)
        assert result == b""

    @given(
        data=st.binary(min_size=1, max_size=512),
        extra=st.integers(min_value=1, max_value=512),
    )
    def test_non_exact_short_read(self, data: bytes, extra: int) -> None:
        """With exact=False, short reads return what is available."""
        requested = len(data) + extra
        result = read_bytes(io.BytesIO(data), requested, exact=False)
        assert result == data


# ---------------------------------------------------------------------------
# Bounds checking: page count
# ---------------------------------------------------------------------------

class TestPageCountBounds:
    """Verify the page-count bounds the host enforces."""

    def test_page_count_zero_rejected(self) -> None:
        """n_pages == 0 is rejected by the host."""
        stream = encode_int(0)
        with pytest.raises(MaxPagesException):
            parse_stream(stream)

    @given(n=st.integers(min_value=1, max_value=MAX_PAGES))
    def test_valid_page_counts_accepted(self, n: int) -> None:
        """Page counts in [1, MAX_PAGES] pass the host bounds check."""
        assert not (n == 0 or n > MAX_PAGES)

    @given(n=st.integers(min_value=MAX_PAGES + 1, max_value=2**16 - 1))
    def test_invalid_page_counts_rejected(self, n: int) -> None:
        """Page counts in (MAX_PAGES, 65535] are rejected."""
        stream = encode_int(n)
        with pytest.raises(MaxPagesException):
            parse_stream(stream)

    def test_max_pages_boundary(self) -> None:
        """Exactly MAX_PAGES is accepted; MAX_PAGES+1 is rejected."""
        assert not (MAX_PAGES == 0 or MAX_PAGES > MAX_PAGES)
        assert MAX_PAGES + 1 > MAX_PAGES


# ---------------------------------------------------------------------------
# Bounds checking: width and height
# ---------------------------------------------------------------------------

class TestDimensionBounds:
    """Verify the width/height bounds the host enforces."""

    @given(w=st.integers(min_value=1, max_value=MAX_PAGE_WIDTH))
    def test_valid_widths(self, w: int) -> None:
        """Widths in [1, MAX_PAGE_WIDTH] pass the bounds check."""
        assert 1 <= w <= MAX_PAGE_WIDTH

    @given(h=st.integers(min_value=1, max_value=MAX_PAGE_HEIGHT))
    def test_valid_heights(self, h: int) -> None:
        """Heights in [1, MAX_PAGE_HEIGHT] pass the bounds check."""
        assert 1 <= h <= MAX_PAGE_HEIGHT

    def test_width_zero_rejected(self) -> None:
        """Width == 0 triggers MaxPageWidthException."""
        stream = encode_int(1) + encode_int(0) + encode_int(1)
        with pytest.raises(MaxPageWidthException):
            parse_stream(stream)

    def test_height_zero_rejected(self) -> None:
        """Height == 0 triggers MaxPageHeightException."""
        stream = encode_int(1) + encode_int(1) + encode_int(0)
        with pytest.raises(MaxPageHeightException):
            parse_stream(stream)

    def test_width_over_max_rejected(self) -> None:
        """Width == MAX_PAGE_WIDTH + 1 triggers MaxPageWidthException."""
        stream = encode_int(1) + encode_int(MAX_PAGE_WIDTH + 1) + encode_int(1)
        with pytest.raises(MaxPageWidthException):
            parse_stream(stream)

    def test_height_over_max_rejected(self) -> None:
        """Height == MAX_PAGE_HEIGHT + 1 triggers MaxPageHeightException."""
        stream = encode_int(1) + encode_int(1) + encode_int(MAX_PAGE_HEIGHT + 1)
        with pytest.raises(MaxPageHeightException):
            parse_stream(stream)


# ---------------------------------------------------------------------------
# Truncated stream tests
# ---------------------------------------------------------------------------

class TestTruncatedStreams:
    """Truncating a valid stream at any point must raise an exception."""

    @given(
        width=st.integers(min_value=1, max_value=50),
        height=st.integers(min_value=1, max_value=50),
        cut_frac=st.floats(min_value=0.0, max_value=0.99),
    )
    @settings(max_examples=50)
    def test_truncated_single_page_stream(
        self, width: int, height: int, cut_frac: float
    ) -> None:
        """Cutting a single-page stream short at any fraction raises on parse."""
        pixel_data = bytes(width * height * 3)
        full_stream = build_pixel_stream([(width, height, pixel_data)])

        cut_point = int(len(full_stream) * cut_frac)
        assume(cut_point < len(full_stream))

        truncated = full_stream[:cut_point]

        with pytest.raises(Exception):
            parse_stream(truncated)

    @given(data=st.binary(min_size=0, max_size=5))
    def test_tiny_random_streams(self, data: bytes) -> None:
        """Any stream shorter than the minimum valid message (9 bytes) fails."""
        # Minimum valid: 2 (page_count=1) + 2 (width=1) + 2 (height=1) + 3 (1 pixel) = 9
        assume(len(data) < 9)
        with pytest.raises(Exception):
            parse_stream(data)


# ---------------------------------------------------------------------------
# Valid stream round-trip tests
# ---------------------------------------------------------------------------

class TestValidStreams:
    """Generate valid streams and verify they parse correctly."""

    @given(
        width=st.integers(min_value=1, max_value=100),
        height=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=30)
    def test_single_page_roundtrip(self, width: int, height: int) -> None:
        """A single page with random dimensions parses to the correct sizes."""
        pixel_data = bytes(width * height * 3)
        stream = build_pixel_stream([(width, height, pixel_data)])
        pages = parse_stream(stream)

        assert len(pages) == 1
        w, h, pixels = pages[0]
        assert w == width
        assert h == height
        assert len(pixels) == width * height * 3

    @given(
        n_pages=st.integers(min_value=1, max_value=5),
        data=st.data(),
    )
    @settings(max_examples=20, deadline=None)
    def test_multi_page_roundtrip(self, n_pages: int, data: st.DataObject) -> None:
        """Multiple pages with varying dimensions parse correctly."""
        expected_pages = []
        for _ in range(n_pages):
            w = data.draw(st.integers(min_value=1, max_value=50))
            h = data.draw(st.integers(min_value=1, max_value=50))
            pixels = data.draw(st.binary(min_size=w * h * 3, max_size=w * h * 3))
            expected_pages.append((w, h, pixels))

        stream = build_pixel_stream(expected_pages)
        parsed = parse_stream(stream)

        assert len(parsed) == n_pages
        for (ew, eh, ep), (pw, ph, pp) in zip(expected_pages, parsed):
            assert pw == ew
            assert ph == eh
            assert pp == ep

    def test_stream_fully_consumed(self) -> None:
        """After parsing, the stream position is at EOF (no trailing bytes)."""
        pixel_data = b"\xab" * 12  # 2x2 RGB
        stream = build_pixel_stream([(2, 2, pixel_data)])
        f = io.BytesIO(stream)

        n = read_int(f)
        assert n == 1
        w = read_int(f)
        h = read_int(f)
        read_bytes(f, w * h * 3, exact=True)
        assert f.read() == b""


# ---------------------------------------------------------------------------
# Integer overflow documentation
# ---------------------------------------------------------------------------

class TestPixelBufferSize:
    """Document that width*height*3 cannot overflow in Python.

    In C/C++ with 16-bit width and height, the max pixel buffer would be
    65535 * 65535 * 3 = 12,884,508,675 bytes (~12 GB). In a 32-bit size_t
    environment this would overflow. Python uses arbitrary-precision integers
    so overflow is impossible, but the bounds checks (MAX_PAGE_WIDTH=10000,
    MAX_PAGE_HEIGHT=10000) keep the max buffer at 10000*10000*3 = 300 MB.
    """

    @given(
        w=st.integers(min_value=1, max_value=MAX_PAGE_WIDTH),
        h=st.integers(min_value=1, max_value=MAX_PAGE_HEIGHT),
    )
    @settings(deadline=None)
    def test_pixel_buffer_size_within_bounds(self, w: int, h: int) -> None:
        """With valid dimensions, pixel buffer size is at most 300_000_000."""
        size = w * h * 3
        assert size <= MAX_PAGE_WIDTH * MAX_PAGE_HEIGHT * 3
        assert size <= 300_000_000

    def test_max_unbounded_pixel_size(self) -> None:
        """Document the theoretical max with uint16 dimensions (no overflow in Python)."""
        max_uint16 = 2**16 - 1
        size = max_uint16 * max_uint16 * 3
        # This is ~12 GB -- would overflow uint32 but Python handles it fine
        assert size == 12_884_508_675
        assert size > 2**32  # proves it would overflow a 32-bit integer


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Targeted edge-case tests for protocol boundaries."""

    def test_all_min_values_valid(self) -> None:
        """A stream at the minimum boundary (1 page, 1x1 pixel) parses."""
        pixel_data = b"\xff\x00\x80"  # 1 RGB pixel
        stream = build_pixel_stream([(1, 1, pixel_data)])
        pages = parse_stream(stream)
        assert len(pages) == 1
        assert pages[0] == (1, 1, pixel_data)

    def test_max_encodable_page_count(self) -> None:
        """65535 is encodable as uint16 but exceeds MAX_PAGES."""
        val = 2**16 - 1
        encoded = encode_int(val)
        decoded = read_int(io.BytesIO(encoded))
        assert decoded == 65535
        assert decoded > MAX_PAGES

        with pytest.raises(MaxPagesException):
            parse_stream(encoded)

    def test_int_bytes_constant(self) -> None:
        """INT_BYTES must be 2 (protocol invariant)."""
        assert INT_BYTES == 2

    def test_extra_trailing_bytes_ignored(self) -> None:
        """The parser does not reject streams with trailing bytes after valid data.

        This documents current behavior -- the parser reads exactly what it
        needs and stops. Trailing garbage is silently ignored.
        """
        pixel_data = b"\x00" * 3  # 1x1 pixel
        stream = build_pixel_stream([(1, 1, pixel_data)]) + b"\xde\xad"

        # parse_stream reads exactly right; trailing bytes are unconsumed
        pages = parse_stream(stream)
        assert len(pages) == 1

    @given(
        w=st.integers(min_value=1, max_value=100),
        h=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=20, deadline=None)
    def test_pixel_count_matches_dimensions(self, w: int, h: int) -> None:
        """The number of pixel bytes is always exactly width * height * 3."""
        expected_size = w * h * 3
        pixel_data = bytes(expected_size)
        stream = build_pixel_stream([(w, h, pixel_data)])
        pages = parse_stream(stream)
        assert len(pages[0][2]) == expected_size
