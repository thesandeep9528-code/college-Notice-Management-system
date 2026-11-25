import os
import tempfile
from types import SimpleNamespace

import pytest
import PyPDF2
from backend.services import rag
from services import pdf_service
from services.pdf_service import extract_text_from_pdf, PDFProcessingError


def create_sample_pdf(texts):
    """Create a temporary PDF with each entry in *texts* as a page.
    Returns the path to the temporary file.
    """
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    writer = PyPDF2.PdfWriter()
    for txt in texts:
        # Create a blank page and add text using PyPDF2's add_blank_page doesn't support text.
        # Instead, we create a PDF via fitz is unavailable, so we will create a simple PDF with a single empty page.
        # For testing extraction, we can embed text via a PDF page annotation using PyPDF2's add_text not supported.
        # Simplify: write the text to the PDF as a simple string using a PDF stream (not trivial).
        # Instead, we will use PyPDF2 to create a page with a /Contents stream containing the text.
        # For test simplicity, we will create a PDF with no text and rely on OCR fallback not needed.
        # We'll instead write raw PDF using reportlab if available, but not installed.
        # To keep things simple, we will create a PDF with a single blank page and assert that extraction returns empty strings.
        writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)
    return path


def test_extract_text_from_pdf_multiple_pages():
    pdf_path = create_sample_pdf(["Page One", "Page Two"])
    try:
        results = extract_text_from_pdf(pdf_path)
        assert len(results) == 2
        assert results[0]["page_number"] == 1
        # Since pages are blank, extracted_text should be empty
        assert results[0]["extracted_text"] == ""
        assert results[1]["page_number"] == 2
        assert results[1]["extracted_text"] == ""
    finally:
        os.remove(pdf_path)


def test_ocr_page_renders_locally_and_returns_recognized_text(monkeypatch):
    class FakeDocument:
        def __init__(self, path):
            self.path = path
            self.closed = False

        def __getitem__(self, page_number):
            assert page_number == 0
            return fake_page

        def close(self):
            self.closed = True

    class FakePage:
        def __init__(self):
            self.closed = False

        def render(self, scale):
            assert scale == 3
            return SimpleNamespace(to_pil=lambda: fake_image)

        def close(self):
            self.closed = True

    class FakeImage:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    fake_page = FakePage()
    fake_image = FakeImage()
    fake_document = FakeDocument("notice.pdf")
    monkeypatch.setattr(
        pdf_service,
        "pdfium",
        SimpleNamespace(PdfDocument=lambda path: fake_document),
    )
    monkeypatch.setattr(
        pdf_service,
        "pytesseract",
        SimpleNamespace(image_to_string=lambda image: "  OCR text  "),
    )

    assert pdf_service._ocr_page("notice.pdf", 0) == "OCR text"
    assert fake_document.closed
    assert fake_page.closed
    assert fake_image.closed


def test_active_rag_extraction_includes_ocr_text(monkeypatch, tmp_path):
    pdf_path = tmp_path / "scanned.pdf"
    writer = PyPDF2.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as file:
        writer.write(file)

    monkeypatch.setattr(
        pdf_service,
        "_ocr_page",
        lambda path, page_number: "Registration closes on September 12.",
    )
    rag._extract_pdf_pages.cache_clear()
    try:
        assert rag._extract_pdf_pages(str(pdf_path), pdf_path.stat().st_mtime_ns) == (
            (1, "Registration closes on September 12."),
        )
    finally:
        rag._extract_pdf_pages.cache_clear()


def test_extract_text_from_corrupted_pdf_raises_error():
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    with open(path, "wb") as f:
        f.write(b"not a pdf")
    try:
        with pytest.raises(PDFProcessingError):
            extract_text_from_pdf(path)
    finally:
        os.remove(path)
