"""OCR for scanned PDF pages and directly uploaded images, via RapidOCR (CPU, onnxruntime
— the same runtime chromadb already pulls in, so this adds no new inference backend).

Kept as its own module, with its own lazily-constructed engine, because it is the one
part of ingestion an admin might reasonably want to switch out (a different OCR engine,
or off entirely — see RAG_OCR_ENABLED) without touching extraction.py's page-assembly
logic.
"""

import logging

logger = logging.getLogger(__name__)

_engine = None


def _get_engine():
    """Lazily construct and cache the RapidOCR engine. Lazy because building it loads an
    onnxruntime session (and, on first-ever run, downloads its model weights), which
    otherwise happens on every worker boot whether or not a document ever needs OCR."""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def reset_engine():
    """Drop the cached engine. For tests."""
    global _engine
    _engine = None


def _text_from_result(result):
    """RapidOCR returns [[box, text, confidence], ...] in reading order (top-to-bottom,
    left-to-right within a line grouping) already, or None when it finds nothing."""
    if not result:
        return ""
    return "\n".join(line[1] for line in result)


def ocr_image(image):
    """Recognize text in `image` (a file path, bytes, or numpy array). Returns "" rather
    than raising when nothing is recognized — an unreadable image is a normal outcome
    the caller decides how to handle, not an engine failure."""
    try:
        result, _ = _get_engine()(image)
    except Exception:
        logger.exception("OCR failed")
        return ""
    return _text_from_result(result)


def ocr_pdf_page(fitz_doc, page_index, zoom=2.0):
    """Rasterize one page of an open PyMuPDF document (0-based `page_index`) and OCR it.

    `zoom` scales the render before recognition: PDF pages default to 72 DPI, which is
    too low for small policy-document print, so this renders at roughly 144 DPI instead.
    """
    import fitz  # PyMuPDF
    import numpy as np
    from PIL import Image

    page = fitz_doc[page_index]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    return ocr_image(np.array(image))
