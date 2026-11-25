import logging
import os
import PyPDF2
from typing import List, Dict

logger = logging.getLogger(__name__)

try:
    import pypdfium2 as pdfium
    import pytesseract
except ImportError as error:  # pragma: no cover
    logger.warning("PDF OCR dependencies are unavailable: %s", error)
    pdfium = None
    pytesseract = None

if pytesseract is not None:
    tesseract_command = os.getenv("TESSERACT_CMD")
    if not tesseract_command and os.name == "nt":
        default_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.isfile(default_tesseract):
            tesseract_command = default_tesseract
    if tesseract_command:
        pytesseract.pytesseract.tesseract_cmd = tesseract_command


class PDFProcessingError(Exception):
    """Raised when a PDF cannot be opened or processed."""


def _ocr_page(pdf_path: str, page_number: int) -> str:
    """Run local OCR on a specific zero-based PDF page.

    Returns extracted text or an empty string if OCR dependencies or the
    Tesseract executable are unavailable.
    """
    if pdfium is None or pytesseract is None:
        logger.warning("OCR skipped for %s page %s: OCR dependencies are unavailable", pdf_path, page_number + 1)
        return ""

    document = None
    page = None
    image = None
    try:
        document = pdfium.PdfDocument(pdf_path)
        page = document[page_number]
        image = page.render(scale=3).to_pil()
        return pytesseract.image_to_string(image).strip()
    except (IndexError, OSError, RuntimeError, ValueError) as error:
        logger.warning(
            "OCR failed for %s page %s: %s",
            pdf_path,
            page_number + 1,
            error,
        )
        return ""
    finally:
        if image is not None:
            image.close()
        if page is not None:
            page.close()
        if document is not None:
            document.close()


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
    except (OSError, PyPDF2.errors.PdfReadError, TypeError, ValueError) as error:
        raise PDFProcessingError(f"Unable to open PDF: {error}") from error

    results: List[Dict] = []
    for page_index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except (KeyError, PyPDF2.errors.PdfReadError, TypeError, ValueError) as error:
            logger.warning("Unable to extract PDF page %s from %s: %s", page_index + 1, pdf_path, error)
            text = ""
        if not text.strip():
            text = _ocr_page(pdf_path, page_index)
        results.append({
            "page_number": page_index + 1,
            "extracted_text": text,
        })
    return results
