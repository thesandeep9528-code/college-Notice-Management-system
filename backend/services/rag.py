import logging
import os
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ..database.queries import get_notices_by_status
from services.pdf_service import PDFProcessingError, extract_text_from_pdf


logger = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "about",
    "and",
    "are",
    "can",
    "could",
    "for",
    "from",
    "how",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "please",
    "tell",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
    "would",
    "you",
}


def _query_terms(text: str) -> list[str]:
    terms = []
    for token in TOKEN_PATTERN.findall(text.lower()):
        if token.endswith("s") and len(token) > 3:
            token = token[:-1]
        if token not in STOP_WORDS and len(token) > 1:
            terms.append(token)
    return terms


def _pdf_path(file_path: Optional[str]) -> Optional[Path]:
    if not file_path or Path(file_path).name != file_path or not file_path.lower().endswith(".pdf"):
        return None
    default_directory = Path(__file__).resolve().parent.parent / "uploads" / "notices"
    root = Path(os.getenv("NOTICE_UPLOAD_DIR", str(default_directory))).resolve()
    candidate = (root / file_path).resolve()
    if root not in candidate.parents or not candidate.is_file():
        return None
    return candidate


# The modification time is part of the cache key so replacing a PDF invalidates its extracted pages.
@lru_cache(maxsize=128)
def _extract_pdf_pages(file_path: str, _modified_time: int) -> tuple[tuple[int, str], ...]:
    try:
        extracted_pages = extract_text_from_pdf(file_path)
    except PDFProcessingError as error:
        logger.warning("Unable to read an approved notice PDF: %s", error)
        return ()

    pages = []
    for extracted_page in extracted_pages:
        page_number = extracted_page["page_number"]
        text = extracted_page["extracted_text"]
        if text.strip():
            pages.append((page_number, text.strip()))
    return tuple(pages)


def _notice_metadata_text(notice: dict) -> str:
    fields = (
        ("Title", notice.get("title")),
        ("Description", notice.get("description")),
        ("Category", notice.get("category")),
        ("Department", notice.get("department")),
        ("Semester", notice.get("semester")),
        ("Deadline", notice.get("deadline")),
    )
    return "\n".join(f"{label}: {value}" for label, value in fields if value)


def _score(text: str, terms: list[str]) -> int:
    frequencies = Counter(_query_terms(text))
    return sum(min(frequencies[term], 3) for term in set(terms))


def _excerpt(text: str, terms: list[str]) -> str:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"\r?\n+", text)
        if sentence.strip()
    ]
    ranked = sorted(
        enumerate(sentences),
        key=lambda item: (-_score(item[1], terms), item[0]),
    )
    specific_terms = [term for term in terms if len(term) > 4]
    if specific_terms:
        best = [sentence for sentence in sentences if any(term in sentence.lower() for term in specific_terms)]
    else:
        best = [sentence for _, sentence in ranked if _score(sentence, terms)]
    excerpt = " ".join(best) if best else " ".join(text.split())
    return excerpt[:4000]


def retrieve_sources(
    question: str,
    top_k: int = 5,
    history: Optional[list[dict]] = None,
    notice_id: Optional[int] = None,
) -> list[dict]:
    """Return matching excerpts from approved notices without external model calls."""
    previous_questions = [
        message["content"]
        for message in (history or [])[-6:]
        if message.get("role") == "user" and message.get("content")
    ]
    terms = _query_terms(" ".join([*previous_questions, question]))
    if not terms:
        return []

    candidates = []
    for notice in get_notices_by_status(status="approved"):
        if notice_id is not None and int(notice["id"]) != notice_id:
            continue
        metadata_text = _notice_metadata_text(notice)
        pdf_path = _pdf_path(notice.get("file_path"))
        pages = ()
        if pdf_path:
            pages = _extract_pdf_pages(str(pdf_path), pdf_path.stat().st_mtime_ns)

        if pages:
            page_matches = [
                (page_number, page_text, _score(page_text, terms))
                for page_number, page_text in pages
            ]
            page_matches = [match for match in page_matches if match[2]]
            if not page_matches and pages:
                page_matches = [(page_number, page_text, 1) for page_number, page_text in pages]
            documents = page_matches or [
                (None, metadata_text, _score(metadata_text, terms))
            ]
        else:
            documents = [(None, metadata_text, _score(metadata_text, terms))]

        for page_number, document, score in documents:
            if not score:
                continue
            candidates.append(
                {
                    "notice_id": notice["id"],
                    "title": notice["title"],
                    "file_name": notice.get("file_name"),
                    "page_number": page_number,
                    "has_file": bool(pdf_path),
                    "excerpt": _excerpt(document, terms),
                    "score": score,
                    "created_at": notice.get("created_at") or "",
                }
            )

    candidates.sort(
        key=lambda item: (item["score"], item["created_at"], item["notice_id"]),
        reverse=True,
    )
    sources = [
        {key: value for key, value in item.items() if key not in {"score", "created_at"}}
        for item in candidates[:top_k]
    ]
    return sources


def answer_question(
    question: str,
    top_k: int = 5,
    history: Optional[list[dict]] = None,
) -> dict:
    """Return matching excerpts from approved notices without external model calls."""
    sources = retrieve_sources(question, top_k=top_k, history=history)
    if not sources:
        return {
            "answer": "I couldn't find that information in the approved notices.",
            "sources": [],
        }

    excerpts = "\n\n".join(f"- {source['excerpt']}" for source in sources)
    return {
        "answer": f"Relevant excerpts from approved notices:\n\n{excerpts}",
        "sources": sources,
    }
