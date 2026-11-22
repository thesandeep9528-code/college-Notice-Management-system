import os
import re
import hashlib
from .pdf_service import extract_text_from_pdf, PDFProcessingError
from .sqlite_helper import init_sqlite, insert_notice_intel, check_duplicate_hash, update_notice_intel

# Simple keyword-based categorization
CATEGORY_KEYWORDS = {
    "examination": "Examination",
    "exam": "Examination",
    "placement": "Placement",
    "scholarship": "Scholarship",
    "academic": "Academic",
    "event": "Events",
    "general": "General",
}

DATE_REGEX = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b", re.IGNORECASE)


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of a file's contents."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def auto_categorize(text: str) -> str:
    """Return a category based on keyword presence; fallback to 'General'."""
    lowered = text.lower()
    for kw, cat in CATEGORY_KEYWORDS.items():
        if kw in lowered:
            return cat
    return "General"


def summarize_text(text: str, max_len: int = 200) -> str:
    """Return a short summary – first sentence(s) up to max_len characters."""
    # Simple heuristic: split on periods
    sentences = [s.strip() for s in re.split(r"[.!?]", text) if s.strip()]
    summary = " ".join(sentences[:2])
    return summary[:max_len]


def extract_deadline(text: str) -> str:
    """Find the first date-like string in the text; return ISO format if possible.
    Returns None if no date found.
    """
    match = DATE_REGEX.search(text)
    if not match:
        return None
    raw_date = match.group(0)
    # Try to parse with dateutil if available, otherwise return raw string
    try:
        from dateutil import parser
        dt = parser.parse(raw_date, dayfirst=False)
        return dt.isoformat()
    except Exception:
        return raw_date


def process_notice_intelligence(notice_id: int, pdf_path: str) -> dict:
    """Extract intelligence from a PDF and store it in SQLite.

    Returns a dict with extracted fields (category, summary, deadline, file_hash).
    """
    init_sqlite()
    # Compute hash and check duplicate
    file_hash = compute_file_hash(pdf_path)
    if check_duplicate_hash(file_hash):
        raise ValueError("Duplicate notice detected based on file hash.")

    # Extract text from PDF
    try:
        pages = extract_text_from_pdf(pdf_path)
    except PDFProcessingError as e:
        raise RuntimeError(f"Failed to extract PDF text: {e}")
    full_text = " ".join(p.get("extracted_text", "") for p in pages)
    # Auto-generate metadata
    category = auto_categorize(full_text)
    summary = summarize_text(full_text)
    deadline = extract_deadline(full_text)
    # Store in SQLite
    insert_notice_intel(notice_id, category, summary, deadline, file_hash)
    return {
        "category": category,
        "summary": summary,
        "deadline": deadline,
        "file_hash": file_hash,
    }

def update_intelligence(notice_id: int, category: str = None, summary: str = None, deadline: str = None):
    """Faculty‑editable update of intelligence fields."""
    update_notice_intel(notice_id, category, summary, deadline)
