import os
from typing import List, Dict
import openai
# If the OpenAI package is not installed (e.g., in test environments), provide a fallback.
try:
    import openai
except ImportError:  # pragma: no cover
    class _DummyOpenAI:
        @staticmethod
        def embeddings():
            class _Create:
                @staticmethod
                def create(input, model):
                    # Return a dummy embedding vector of zeros (length 1536 for text-embedding-3-large).
                    return type('obj', (object,), {'data': [type('d', (object,), {'embedding': [0.0] * 1536})]})
            return _Create()
    openai = _DummyOpenAI()

import chromadb
from chromadb.utils import embedding_functions
from services.pdf_service import extract_text_from_pdf, PDFProcessingError
from database.queries import get_notices_by_status

# Environment variable for OpenAI API key (must be set externally)
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable not set")
openai.api_key = openai_api_key

# Initialize persistent ChromaDB client and collection
CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "chromadb")
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_or_create_collection(
    name="notice_chunks",
    metadata={"hnsw:space": "cosine"},
    # Use OpenAI embeddings via built‑in embedding function for convenience
    embedding_function=embedding_functions.OpenAIEmbeddingFunction(
        api_key=openai_api_key,
        model_name="text-embedding-3-large"
    ),
)

# Simple chunking parameters – can be tuned later
CHUNK_SIZE = 500  # characters
CHUNK_OVERLAP = 50  # characters


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split *text* into overlapping chunks.

    Returns a list of string chunks.
    """
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def _embed_text(text: str) -> List[float]:
    """Obtain an embedding vector for *text* using OpenAI embeddings.
    """
    # Using the OpenAI SDK – latest method call
    response = openai.embeddings.create(input=text, model="text-embedding-3-large")
    # The response format contains a list of embeddings; we take the first
    return response.data[0].embedding


def _notice_already_processed(notice_id: int) -> bool:
    """Check if any chunk with the given notice_id exists in the collection.
    """
    results = collection.get(where={"notice_id": notice_id}, include=["metadatas"], limit=1)
    return bool(results.get("ids"))


def process_approved_notices() -> None:
    """Process all notices with status='approved' and store their text chunks.

    This function can be called periodically (e.g., after a new notice is approved).
    It avoids re‑processing notices that are already in the vector store.
    """
    approved = get_notices_by_status("approved")
    for notice in approved:
        notice_id = notice["id"]
        if _notice_already_processed(notice_id):
            continue
        pdf_path = notice.get("file_path")
        if not pdf_path or not os.path.isfile(pdf_path):
            # Skip if the PDF is missing – could log a warning in a real app
            continue
        try:
            pages = extract_text_from_pdf(pdf_path)
        except PDFProcessingError:
            continue
        for page in pages:
            page_num = page["page_number"]
            text = page["extracted_text"].strip()
            if not text:
                continue
            chunks = _chunk_text(text)
            for idx, chunk in enumerate(chunks):
                doc_id = f"{notice_id}_{page_num}_{idx}"
                metadata = {
                    "notice_id": notice_id,
                    "page_number": page_num,
                    "chunk_index": idx,
                    "filename": os.path.basename(pdf_path),
                }
                # Compute embedding – Chroma can compute automatically using the embedding function,
                # but we store explicit embeddings here for clarity.
                embedding = _embed_text(chunk)
                collection.add(
                    ids=[doc_id],
                    documents=[chunk],
                    metadatas=[metadata],
                    embeddings=[embedding],
                )


def search_similar(query: str, top_k: int = 5) -> List[Dict]:
    """Search the Chroma collection for *query* text and return matching chunks.

    Returns a list of dictionaries containing ``id``, ``document``, ``metadata`` and ``distance``.
    """
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances", "ids"],
    )
    # The query returns lists for each field – unpack the first (and only) query
    output = []
    for doc_id, doc, meta, dist in zip(
        results.get("ids", [[]])[0],
        results.get("documents", [[]])[0],
        results.get("metadatas", [[]])[0],
        results.get("distances", [[]])[0],
    ):
        output.append({
            "id": doc_id,
            "document": doc,
            "metadata": meta,
            "distance": dist,
        })
    return output
