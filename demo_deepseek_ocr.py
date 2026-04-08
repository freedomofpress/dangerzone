#!/usr/bin/env python3
"""Demo: DeepSeek-OCR-3B vs Tesseract in dangerzone.

Converts a document using both OCR backends and compares results.
Requires: pip install -e ".[deepseek]" (or torch + transformers + einops)

Usage:
    python demo_deepseek_ocr.py <input_file> [--backend deepseek|tesseract|both]

Examples:
    python demo_deepseek_ocr.py test.pdf --backend deepseek
    python demo_deepseek_ocr.py scan.png --backend both
"""

import argparse
import sys
import tempfile
import time
from pathlib import Path

import fitz


def ocr_with_deepseek(image_path: str) -> tuple[str, float]:
    """Run DeepSeek-OCR on an image file. Returns (text, elapsed_seconds)."""
    from dangerzone.deepseek_ocr import ocr_page

    img = fitz.open(image_path)
    results = []
    total_time = 0.0

    for page_num in range(len(img)):
        page = img[page_num]
        pix = page.get_pixmap(dpi=150)
        rgb_bytes = pix.samples  # raw RGB

        start = time.perf_counter()
        text = ocr_page(rgb_bytes, pix.width, pix.height)
        elapsed = time.perf_counter() - start
        total_time += elapsed

        results.append(f"--- Page {page_num + 1} ({elapsed:.2f}s) ---\n{text}")

    return "\n\n".join(results), total_time


def ocr_with_tesseract(image_path: str, lang: str = "eng") -> tuple[str, float]:
    """Run Tesseract OCR via PyMuPDF on an image file. Returns (text, elapsed_seconds)."""
    img = fitz.open(image_path)
    results = []
    total_time = 0.0

    for page_num in range(len(img)):
        page = img[page_num]
        pix = page.get_pixmap(dpi=150)

        start = time.perf_counter()
        # Use PyMuPDF's built-in Tesseract to get a searchable PDF, then extract text
        pdf_bytes = pix.pdfocr_tobytes(compress=True, language=lang)
        pdf_doc = fitz.open("pdf", pdf_bytes)
        text = ""
        for p in pdf_doc:
            text += p.get_text()
        elapsed = time.perf_counter() - start
        total_time += elapsed

        results.append(f"--- Page {page_num + 1} ({elapsed:.2f}s) ---\n{text}")

    return "\n\n".join(results), total_time


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek-OCR vs Tesseract demo")
    parser.add_argument("input_file", help="PDF or image file to OCR")
    parser.add_argument(
        "--backend",
        choices=["deepseek", "tesseract", "both"],
        default="both",
        help="Which OCR backend to use (default: both)",
    )
    parser.add_argument(
        "--lang", default="eng", help="Tesseract language code (default: eng)"
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)

    print(f"Input: {input_path}")
    print(f"Backend: {args.backend}")
    print()

    if args.backend in ("tesseract", "both"):
        print("=" * 60)
        print("TESSERACT OCR")
        print("=" * 60)
        text, elapsed = ocr_with_tesseract(str(input_path), args.lang)
        print(text)
        print(f"\nTesseract total: {elapsed:.2f}s")
        print()

    if args.backend in ("deepseek", "both"):
        print("=" * 60)
        print("DEEPSEEK-OCR-3B")
        print("=" * 60)
        text, elapsed = ocr_with_deepseek(str(input_path))
        print(text)
        print(f"\nDeepSeek total: {elapsed:.2f}s")
        print()


if __name__ == "__main__":
    main()
