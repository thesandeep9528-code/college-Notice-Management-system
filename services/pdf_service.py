import os
import PyPDF2
from typing import List, Dict

# Optional OCR imports – they may not be available in all environments
try:
    from pdf2image import convert_from_path
    import pytesseract
except Exception:  # pragma: no cover
    convert_from_path = None
    pytesseract = None


class PDFProcessingError(Exception):
    """Raised when a PDF cannot be opened or processed."""


def _ocr_page(pdf_path: str, page_number: int) -> str:
    """Fallback OCR for a specific page using pdf2image and pytesseract.

    Returns extracted text or an empty string if OCR fails.
    """
    if convert_from_path is None or pytesseract is None:
        return ""
    try:
        images = convert_from_path(pdf_path, first_page=page_number + 1, last_page=page_number + 1)
        if not images:
            return ""
        img = images[0]
        return pytesseract.image_to_string(img)
    except Exception:  # pragma: no cover
        return ""


def extract_text_from_pdf(pdf_path: str) -> List[Dict]:
    """Extract text from a PDF, page by page using PyPDF2.

    Parameters
    ----------
    pdf_path: str
        Path to the PDF file.

    Returns
    -------
    List[Dict]
        A list where each dict contains ``page_number`` (1‑based) and
        ``extracted_text`` (the raw string). If a page yields no text via
        PyPDF2, an OCR fallback is attempted; the result (even if empty) is
        still stored.

    Raises
    ------
    PDFProcessingError
        If the file cannot be opened as a PDF.
    """
    if not os.path.isfile(pdf_path):
        raise PDFProcessingError(f"File not found: {pdf_path}")
    try:
        reader = PyPDF2.PdfReader(pdf_path)
    except Exception as e:
        raise PDFProcessingError(f"Unable to open PDF: {e}")

    results: List[Dict] = []
    for page_index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if not text.strip():
            text = _ocr_page(pdf_path, page_index)
        results.append({
            "page_number": page_index + 1,
            "extracted_text": text,
        })
    return results
