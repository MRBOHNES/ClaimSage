"""OCR helpers for content that has no extractable text layer.

Two callers:
  * ``ocr_page``       — a scanned PDF page, rasterized via PyMuPDF (no external
                         ImageMagick/poppler needed) and passed to Tesseract.
  * ``ocr_image_file`` — a plain image upload (e.g. a phone photo of a document).

Both are deliberately defensive: OCR failures return an empty string and log a
warning rather than raising, so one unreadable page never fails a whole upload
(ingestion runs detached as a background task). ``pytesseract`` / ``Pillow`` are
imported lazily so the rest of the app doesn't hard-depend on the Tesseract
binary being installed when OCR is disabled.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

import fitz  # pymupdf

logger = logging.getLogger(__name__)


def ocr_page(page: fitz.Page, dpi: int, lang: str) -> str:
    """Rasterize a PDF page to an image and OCR it. Returns "" on any failure."""
    try:
        import pytesseract
        from PIL import Image

        pixmap = page.get_pixmap(dpi=dpi)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        return pytesseract.image_to_string(image, lang=lang).strip()
    except Exception as e:  # noqa: BLE001 - OCR must never break ingestion
        logger.warning("OCR failed for page %s: %s", getattr(page, "number", "?"), e)
        return ""


def ocr_image_file(file_path: str | Path, lang: str) -> str:
    """OCR an image file (jpg/png/tiff/bmp). Returns "" on any failure."""
    try:
        import pytesseract
        from PIL import Image

        with Image.open(file_path) as image:
            return pytesseract.image_to_string(image, lang=lang).strip()
    except Exception as e:  # noqa: BLE001 - OCR must never break ingestion
        logger.warning("OCR failed for image %s: %s", file_path, e)
        return ""
