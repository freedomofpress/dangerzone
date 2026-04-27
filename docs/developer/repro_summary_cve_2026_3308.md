# Reproduction Summary: CVE-2026-3308 (MuPDF Stride Overflow)

## Vulnerability Overview
MuPDF (and by extension PyMuPDF) contains an integer overflow in the stride calculation within the image unpacking pipeline. While a partial fix was attempted in the 1.27.x era, it failed to account for a zero-wrap ($2^{32}$), leaving the library vulnerable to a `SIGSEGV` crash.

### Vulnerable Code Path
- **File:** `source/fitz/draw-unpack.c`
- **Function:** `fz_unpack_stream`
- **Logic:** `int src_stride = (w * depth * n + 7) >> 3;`

### The "Zero-Wrap" Attack Vector
For a 16-bit CMYK image (depth=16, n=4), a width of **67,108,864** ($2^{26}$) results in a product of exactly $2^{32}$. 
1. The 32-bit `int` product wraps to **0**.
2. `src_stride` becomes **0**.
3. `fz_malloc` allocates a tiny buffer (header only).
4. `fz_decomp_image_from_stream` attempts to write the full image row into the tiny buffer.
5. **Result:** Immediate heap-based buffer overflow and `SIGSEGV`.

## Upstream Patch Status
- **MuPDF 1.27.0 (Vulnerable):** Pure 32-bit arithmetic; wraps negative at $2^{31}$ and zero at $2^{32}$.
- **MuPDF 1.27.1 / 1.27.2 (Incompletely Patched):** Despite claims of a fix, source audit of these tags reveals the 32-bit logic persists. $2^{31}$ causes a large negative value (graceful malloc failure on 64-bit), but $2^{32}$ causes a crash.
- **Master (Commit `ed461a8e9`):** Implements `fz_ckd_mul_u64` (checked multiplication). This is the definitive fix, but it is not available in any current PyMuPDF release (as of April 2026).

## Dangerzone Impact
This reproduction proves that Dangerzone's **MAX_PAGE_WIDTH=10000** boundary is a necessary and effective security control. It prevents adversarial dimensions from reaching the brittle MuPDF C logic, effectively neutralizing both the $2^{31}$ and $2^{32}$ variants of the overflow.

## Reproduction Steps
```bash
# Triggers SIGSEGV on PyMuPDF <= 1.27.2.2
uv run --no-project --with PyMuPDF python3 -c "import fitz; doc=fitz.open(stream=crafted_pdf); page=doc[0]; page.get_pixmap()"
```
