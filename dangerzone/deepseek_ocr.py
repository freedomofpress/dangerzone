"""DeepSeek-OCR-3B backend for dangerzone.

Replaces Tesseract OCR with DeepSeek-OCR-3B running on a local GPU.
This is a demo integration — requires CUDA GPU with >= 16GB VRAM.

Usage:
    dangerzone-cli --ocr-lang eng --ocr-backend deepseek document.pdf
"""

import logging
import os
import tempfile
from typing import Optional, Tuple

import fitz

from .conversion.common import DEFAULT_DPI

log = logging.getLogger(__name__)

# Lazy-loaded singleton
_model = None
_tokenizer = None


def _ensure_model() -> Tuple:
    """Load DeepSeek-OCR model on first use, reuse thereafter."""
    global _model, _tokenizer
    if _model is not None:
        return _tokenizer, _model

    log.info("Loading DeepSeek-OCR-3B model (first page will be slow)...")

    import torch
    from transformers import AutoModel, AutoTokenizer

    model_name = "deepseek-ai/DeepSeek-OCR"

    _tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

    # Try flash_attention_2 first, fall back to eager if not available
    try:
        _model = AutoModel.from_pretrained(
            model_name,
            _attn_implementation="flash_attention_2",
            trust_remote_code=True,
            use_safetensors=True,
        )
    except (ImportError, ValueError) as e:
        log.warning(f"flash-attn not available ({e}), using eager attention")
        _model = AutoModel.from_pretrained(
            model_name,
            _attn_implementation="eager",
            trust_remote_code=True,
            use_safetensors=True,
        )

    _model = _model.eval().cuda().to(torch.bfloat16)
    log.info("DeepSeek-OCR-3B model loaded successfully")
    return _tokenizer, _model


def ocr_page(
    pixmap_bytes: bytes,
    width: int,
    height: int,
) -> str:
    """Run DeepSeek-OCR on a single page's RGB pixel buffer.

    Args:
        pixmap_bytes: Raw RGB bytes (width * height * 3)
        width: Page width in pixels
        height: Page height in pixels

    Returns:
        Extracted text from the page
    """
    tokenizer, model = _ensure_model()

    # DeepSeek-OCR expects an image file path, so write pixels to a temp PNG
    pixmap = fitz.Pixmap(
        fitz.Colorspace(fitz.CS_RGB),
        width,
        height,
        pixmap_bytes,
        False,
    )
    pixmap.set_dpi(DEFAULT_DPI, DEFAULT_DPI)

    with tempfile.TemporaryDirectory() as tmpdir:
        image_path = os.path.join(tmpdir, "page.png")
        output_path = tmpdir
        pixmap.save(image_path)

        result = model.infer(
            tokenizer,
            prompt="<image>\nFree OCR. ",
            image_file=image_path,
            output_path=output_path,
            base_size=1024,
            image_size=640,
            crop_mode=True,
            save_results=False,
            eval_mode=True,
        )

    if isinstance(result, list):
        return "\n".join(str(r) for r in result)
    return str(result) if result else ""


def ocr_page_to_pdf(
    pixmap_bytes: bytes,
    width: int,
    height: int,
) -> bytes:
    """Run DeepSeek-OCR on a page and return a searchable PDF.

    Creates a PDF page with the original image and an invisible text layer
    containing the OCR'd text, similar to what Tesseract's pdfocr produces.

    Returns:
        PDF bytes for a single searchable page
    """
    text = ocr_page(pixmap_bytes, width, height)

    # Build the base image page
    pixmap = fitz.Pixmap(
        fitz.Colorspace(fitz.CS_RGB),
        width,
        height,
        pixmap_bytes,
        False,
    )
    pixmap.set_dpi(DEFAULT_DPI, DEFAULT_DPI)

    page_doc = fitz.Document()
    page_doc.insert_file(pixmap)

    if text.strip():
        page = page_doc[0]
        rect = page.rect

        # Insert OCR text as an invisible text layer over the image.
        # This makes the PDF searchable/selectable while the image stays visible.
        # We use a very small font with render mode 3 (invisible) via a text writer.
        tw = fitz.TextWriter(rect)
        # Use a standard font, place text starting at top-left
        font = fitz.Font("helv")
        fontsize = 10
        # Split text into lines and place them
        lines = text.split("\n")
        y = 12.0
        for line in lines:
            if not line.strip():
                y += fontsize * 1.2
                continue
            try:
                tw.append((2, y), line, font=font, fontsize=fontsize)
            except Exception:
                pass  # skip lines that can't be rendered
            y += fontsize * 1.2
            if y > rect.height - 10:
                break

        tw.write_text(page, render_mode=3, opacity=0)  # invisible text

    return page_doc.tobytes(deflate_images=True)
