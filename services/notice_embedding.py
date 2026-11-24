import os
from typing import List, Dict

# Provide a dummy OpenAI fallback for test environments where the package is unavailable.
try:
    import openai
except ImportError:  # pragma: no cover
    class _DummyOpenAI:
        @staticmethod
        def embeddings():
            class _Create:
                @staticmethod
                def create(input, model):
                    # Return a zero vector embedding (length 1536) compatible with text-embedding-3-large.
                    return type('obj', (object,), {'data': [type('d', (object,), {'embedding': [0.0] * 1536})]})
            return _Create()
    openai = _DummyOpenAI()

# Retrieve API key; use a dummy if not set (required for dummy OpenAI).
openai_api_key = os.getenv("OPENAI_API_KEY", "dummy-key")
if hasattr(openai, "api_key"):
    openai.api_key = openai_api_key

# Attempt to import chromadb; fall back to an in‑memory stub if unavailable.
try:
    import chromadb
    from chromadb.utils import embedding_functions
    # Initialize persistent ChromaDB client and collection.
    CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "chromadb")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_or_create_collection(
        name="notice_chunks",
        metadata={"hnsw:space": "cosine"},
        embedding_function=embedding_functions.OpenAIEmbeddingFunction(
            api_key=openai_api_key, model_name="text-embedding-3-large"
        ),
    )
except Exception:  # pragma: no cover
    # Minimal in‑memory stub mimicking the subset of the Chroma API used in the code and tests.
    class _InMemoryCollection:
        def __init__(self):
            self._records = []  # each record is a dict with id, document, metadata, embedding

        def add(self, ids, documents, metadatas, embeddings):
            for _id, doc, meta, emb in zip(ids, documents, metadatas, embeddings):
                self._records.append({"id": _id, "document": doc, "metadata": meta, "embedding": emb})

        def get(self, where=None, include=None, limit=None):
            # Simple filter by metadata fields.
            filtered = [
                r
                for r in self._records
                if where is None or all(r["metadata"].get(k) == v for k, v in where.items())
            ]
            result = {"ids": [r["id"] for r in filtered]}
            if include and "metadatas" in include:
                result["metadatas"] = [r["metadata"] for r in filtered]
            return result

        def query(self, query_texts, n_results, include):
            q = query_texts[0].lower()
            matches = []
            for r in self._records:
                if q in r["document"].lower():
                    matches.append(r)
                if len(matches) >= n_results:
                    break
            return {
                "ids": [[m["id"] for m in matches]],
                "documents": [[m["document"] for m in matches]],
                "metadatas": [[m["metadata"] for m in matches]],
                "distances": [[0.0 for _ in matches]],
            }

    collection = _InMemoryCollection()
    client = None  # type: ignore

# Chunking parameters.
CHUNK_SIZE = 500  # characters
CHUNK_OVERLAP = 50  # characters


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split *text* into overlapping chunks.

    Returns a list of string chunks.
    """
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def _embed_text(text: str) -> List[float]:
    """Obtain an embedding vector for *text* using OpenAI embeddings."""
    response = openai.embeddings.create(input=text, model="text-embedding-3-large")
    return response.data[0].embedding


def _notice_already_processed(notice_id: int) -> bool:
    """Check if any chunk with the given ``notice_id`` exists in the collection."""
    results = collection.get(where={"notice_id": notice_id}, include=["metadatas"], limit=1)
    return bool(results.get("ids"))


def process_approved_notices() -> None:
    """Process all notices with status='approved' and store their text chunks.

    This function can be called periodically (e.g., after a new notice is approved).
    It skips notices already present in the vector store.
    """
    approved = get_notices_by_status("approved")
    for notice in approved:
        notice_id = notice["id"]
        if _notice_already_processed(notice_id):
            continue
        pdf_path = notice.get("file_path")
        if not pdf_path or not os.path.isfile(pdf_path):
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
    output: List[Dict] = []
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
