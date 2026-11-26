import hashlib
import json
import logging
import os
import uuid

from .rag import _extract_pdf_pages, _notice_metadata_text, _pdf_path
from services.pdf_service import extract_student_table_rows

logger = logging.getLogger(__name__)
INDEX_SOURCE = "sqlite_approved"
INDEX_BATCH_SIZE = 500


def get_chroma_collection():
    if not os.getenv("OPENAI_API_KEY"):
        return None

    try:
        from services import notice_embedding
    except ImportError as error:
        logger.warning("ChromaDB is unavailable; using local notice retrieval: %s", error)
        return None

    if notice_embedding.client is None:
        return None
    return notice_embedding.collection


def _notice_documents(notice: dict, chunk_text) -> tuple[list[str], list[dict], str]:
    pdf_path = _pdf_path(notice.get("file_path"))
    pages = ()
    if pdf_path:
        try:
            pages = _extract_pdf_pages(str(pdf_path), pdf_path.stat().st_mtime_ns)
        except OSError as error:
            logger.warning("Unable to read PDF metadata for notice %s: %s", notice["id"], error)

    filename = notice.get("file_name") or ""

    # Existing PDF page extraction
    pages = ()
    if pdf_path:
        try:
            pages = _extract_pdf_pages(str(pdf_path), pdf_path.stat().st_mtime_ns)
        except OSError as error:
            logger.warning("Unable to read PDF metadata for notice %s: %s", notice["id"], error)

    # New structured rows extraction
    structured_rows = []
    if pdf_path:
        try:
            structured_rows = extract_student_table_rows(str(pdf_path))
        except Exception as error:
            logger.warning("Failed to extract student rows from notice %s: %s", notice["id"], error)

    filename = notice.get("file_name") or ""
    texts = [(0, _notice_metadata_text(notice), "metadata")]
    texts.extend((page_number, text, "pdf") for page_number, text in pages)
    # Add a synthetic page for each structured row so they get chunked and stored
    for row in structured_rows:
        row_text = f"Roll {row['roll_number']} | {row['student_name']} | CT1 {row['ct1']} | CT2 {row['ct2']}"
        # Use page_number 0 to indicate table row (metadata‑type)
        texts.append((0, row_text, "table_row"))

    texts.extend((page_number, text, "pdf") for page_number, text in pages)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "notice": _notice_metadata_text(notice),
                "filename": filename,
                "pages": pages,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    documents = []
    metadatas = []
    for page_number, text, source_type in texts:
        for chunk_index, chunk in enumerate(chunk_text(text)):
            documents.append(chunk)
            metadatas.append(
                {
                    "notice_id": int(notice["id"]),
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "filename": filename,
                    "title": notice.get("title") or "",
                    "file_name": filename,
                    "has_file": bool(pdf_path),
                    "content_hash": fingerprint,
                    "source": INDEX_SOURCE,
                    "source_type": source_type,
                }
            )
    return documents, metadatas, fingerprint


def sync_approved_notices(notices: list[dict], collection=None) -> bool:
    """Index the current approved SQLite notices in the existing Chroma collection."""
    if collection is None:
        collection = get_chroma_collection()
    if collection is None:
        return False

    from services.notice_embedding import chunk_text

    for notice in notices:
        documents, metadatas, fingerprint = _notice_documents(notice, chunk_text)
        notice_id = int(notice["id"])
        where = {
            "$and": [
                {"notice_id": notice_id},
                {"source": INDEX_SOURCE},
            ]
        }
        existing = collection.get(where=where, include=["metadatas"])
        existing_ids = existing.get("ids", [])
        existing_metadatas = existing.get("metadatas", [])
        if (
            len(existing_ids) == len(documents)
            and len(existing_metadatas) == len(documents)
            and all(
                metadata.get("content_hash") == fingerprint
                for metadata in existing_metadatas
            )
        ):
            continue

        if documents:
            generation_id = uuid.uuid4().hex
            ids = [
                f"sqlite_{notice_id}_{generation_id}_{metadata['page_number']}_{metadata['chunk_index']}_{index}"
                for index, metadata in enumerate(metadatas)
            ]
            for start in range(0, len(documents), INDEX_BATCH_SIZE):
                end = start + INDEX_BATCH_SIZE
                collection.add(
                    ids=ids[start:end],
                    documents=documents[start:end],
                    metadatas=metadatas[start:end],
                )
        if existing_ids:
            collection.delete(ids=existing_ids)
    return True