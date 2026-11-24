import logging
import os
from typing import List, Dict

logger = logging.getLogger(__name__)
openai_api_key = os.getenv("OPENAI_API_KEY")


class _InMemoryCollection:
    def __init__(self):
        self._records = []

    def add(self, ids, documents, metadatas, embeddings=None):
        for index, (record_id, document, metadata) in enumerate(
            zip(ids, documents, metadatas)
        ):
            record = {
                "id": record_id,
                "document": document,
                "metadata": metadata,
            }
            if embeddings is not None:
                record["embedding"] = embeddings[index]
            self._records.append(record)

    def get(self, where=None, include=None, limit=None):
        filtered = [
            record
            for record in self._records
            if self._matches_where(record["metadata"], where)
        ]
        if limit is not None:
            filtered = filtered[:limit]
        result = {"ids": [record["id"] for record in filtered]}
        if include and "metadatas" in include:
            result["metadatas"] = [record["metadata"] for record in filtered]
        return result

    def delete(self, ids=None, where=None):
        removed = set(ids or [])
        self._records = [
            record
            for record in self._records
            if record["id"] not in removed
            and not self._matches_where(record["metadata"], where)
        ]

    def query(self, query_texts, n_results, include, where=None):
        query = query_texts[0].lower()
        matches = [
            record
            for record in self._records
            if self._matches_where(record["metadata"], where)
            and query in record["document"].lower()
        ][:n_results]
        result = {
            "ids": [[record["id"] for record in matches]],
            "documents": [[record["document"] for record in matches]],
            "metadatas": [[record["metadata"] for record in matches]],
        }
        if "distances" in include:
            result["distances"] = [[0.0 for _ in matches]]
        return result

    @staticmethod
    def _matches_where(metadata, where):
        if not where:
            return True
        if "$and" in where and not all(
            _InMemoryCollection._matches_where(metadata, condition)
            for condition in where["$and"]
        ):
            return False
        for key, expected in where.items():
            if key == "$and":
                continue
            value = metadata.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if value not in expected["$in"]:
                    return False
            elif value != expected:
                return False
        return True


client = None
collection = _InMemoryCollection()

if openai_api_key:
    try:
        import chromadb
        from chromadb.errors import ChromaError
        from chromadb.utils import embedding_functions

        chroma_db_path = os.getenv(
            "CHROMA_DB_PATH",
            os.path.join(os.path.dirname(__file__), "..", "chromadb"),
        )
        client = chromadb.PersistentClient(path=chroma_db_path)
        collection = client.get_or_create_collection(
            name="notice_chunks",
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_functions.OpenAIEmbeddingFunction(
                api_key_env_var="OPENAI_API_KEY",
                model_name="text-embedding-3-large",
            ),
        )
    except ImportError as error:  # pragma: no cover
        logger.warning("ChromaDB is unavailable; using local notice retrieval: %s", error)
    except ChromaError as error:  # pragma: no cover
        logger.error("ChromaDB could not open its persistent collection: %s", error)
        client = None

# Chunking parameters.
CHUNK_SIZE = 500  # characters
CHUNK_OVERLAP = 50  # characters


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
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


def process_approved_notices() -> None:
    """Synchronize approved SQLite notices into the persistent Chroma collection."""
    if client is None:
        logger.info("Notice indexing skipped because OpenAI or Chroma is unavailable")
        return

    from backend.database.queries import get_notices_by_status
    from backend.services.rag_index import sync_approved_notices

    sync_approved_notices(
        get_notices_by_status(status="approved"),
        collection=collection,
    )


def search_similar(
    query: str,
    top_k: int = 5,
    where: dict | None = None,
) -> List[Dict]:
    """Search the Chroma collection for *query* text and return matching chunks.

    Returns a list of dictionaries containing ``id``, ``document``, ``metadata`` and ``distance``.
    """
    query_options: dict[str, object] = {
        "query_texts": [query],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances", "ids"],
    }
    if where:
        query_options["where"] = where
    results = collection.query(
        **query_options,
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
