"""
CV Format Tool — OCR Engine
Extracts text from image-based/scanned PDFs using multiple OCR backends.
Priority: pytesseract (Tesseract) → EasyOCR → fallback to PyMuPDF image extraction.
"""

import os
import io
import tempfile
from typing import Optional

# ── Backend availability detection ──────────────────────────────

_TESSERACT_AVAILABLE = False
_EASYOCR_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    _TESSERACT_AVAILABLE = True
except ImportError:
    pass

try:
    import easyocr
    _EASYOCR_AVAILABLE = True
except ImportError:
    pass


def is_ocr_available() -> bool:
    """Check if any OCR backend is installed."""
    return _TESSERACT_AVAILABLE or _EASYOCR_AVAILABLE


def get_ocr_backend() -> str:
    """Return the name of the available OCR backend."""
    if _TESSERACT_AVAILABLE:
        return "tesseract"
    if _EASYOCR_AVAILABLE:
        return "easyocr"
    return "none"


def _ocr_with_tesseract(images: list, lang: str = "eng+vie") -> str:
    """OCR using Tesseract via pytesseract."""
    texts = []
    for img in images:
        try:
            text = pytesseract.image_to_string(img, lang=lang)
            if text.strip():
                texts.append(text.strip())
        except Exception as e:
            print(f"[OCR/Tesseract] Page error: {e}")
            continue
    return "\n\n".join(texts)


def _ocr_with_easyocr(images: list, lang: list[str] = None) -> str:
    """OCR using EasyOCR."""
    if lang is None:
        lang = ["en", "vi"]

    reader = easyocr.Reader(lang, gpu=False)
    texts = []

    for img in images:
        try:
            # EasyOCR can work with PIL Image or numpy array
            import numpy as np
            img_array = np.array(img)
            results = reader.readtext(img_array, detail=0, paragraph=True)
            page_text = "\n".join(results)
            if page_text.strip():
                texts.append(page_text.strip())
        except Exception as e:
            print(f"[OCR/EasyOCR] Page error: {e}")
            continue

    return "\n\n".join(texts)


def extract_text_from_scanned_pdf(pdf_path: str, lang: str = "auto") -> str:
    """
    Extract text from a scanned/image-based PDF using OCR.

    Args:
        pdf_path: Path to the PDF file
        lang: Language hint — "vi", "en", or "auto" (tries both)

    Returns:
        Extracted text string. Empty string if OCR fails or is unavailable.
    """
    if not is_ocr_available():
        return ""

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ""

    # Convert PDF pages to images
    doc = fitz.open(pdf_path)
    images = []

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render page at 300 DPI for good OCR quality
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            from PIL import Image
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)

        if not images:
            return ""

        # Try OCR backends in priority order
        if _TESSERACT_AVAILABLE:
            tesseract_lang = "eng+vie" if lang in ("auto", "vi") else "eng"
            text = _ocr_with_tesseract(images, lang=tesseract_lang)
            if text.strip():
                return text

        if _EASYOCR_AVAILABLE:
            easyocr_lang = ["en", "vi"] if lang in ("auto", "vi") else ["en"]
            text = _ocr_with_easyocr(images, lang=easyocr_lang)
            if text.strip():
                return text

        return ""

    except Exception as e:
        print(f"[OCR] Failed to process {pdf_path}: {e}")
        return ""
    finally:
        doc.close()
        # Clean up PIL images
        for img in images:
            try:
                img.close()
            except Exception:
                pass


def is_scanned_pdf(pdf_path: str, min_text_ratio: float = 0.01) -> bool:
    """
    Detect if a PDF is likely scanned (image-based) rather than text-based.

    Heuristic: If the PDF has very little extractable text relative to its
    page count, it's likely scanned.

    Args:
        pdf_path: Path to the PDF file
        min_text_ratio: Minimum chars per page to consider it text-based

    Returns:
        True if the PDF appears to be scanned/image-based
    """
    try:
        import fitz
        doc = fitz.open(pdf_path)
        total_text = ""
        page_count = len(doc)

        for page in doc:
            total_text += page.get_text()

        doc.close()

        if page_count == 0:
            return True

        chars_per_page = len(total_text.strip()) / page_count
        # If less than 50 chars per page on average, likely scanned
        return chars_per_page < 50

    except Exception:
        return False
