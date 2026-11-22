import os
import google.generativeai as genai
from .notice_embedding import search_similar

# Initialize Gemini model (lazy configuration)
def _configure_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)


def retrieve_relevant_chunks(question: str, top_k: int = 5):
    """Search ChromaDB for chunks relevant to *question*.
    Returns list of dicts with keys: id, document, metadata, distance.
    """
    return search_similar(question, top_k=top_k)


def answer_question(question: str, top_k: int = 5) -> str:
    """Perform RAG: retrieve chunks, generate answer via Gemini, and attach reliable citations.

    The function now formats a citation block using the ``filename`` and ``page_number``
    metadata stored for each chunk. Duplicate citations (same file & page) are de‑duplicated
    to avoid repetition. If no relevant chunks are found, a clear fallback message is
    returned. The answer string includes the citation block so the UI can simply display
    the returned value.
    """
    # Ensure Gemini is configured
    _configure_gemini()
    chunks = retrieve_relevant_chunks(question, top_k=top_k)
    if not chunks:
        return "I could not find relevant notice information."
    # Build context from chunk documents
    context = "\n---\n".join(chunk["document"] for chunk in chunks if chunk.get("document"))
    prompt = (
        "Answer the following question using ONLY the provided context. "
        "If the answer cannot be found in the context, explicitly state that the notice information could not be found. "
        "Do NOT invent dates, deadlines, or any information not present in the context.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    answer_text = response.text.strip() if response and getattr(response, 'text', None) else "Unable to generate answer."
    # -------------------------------------------------------------------
    # Citation handling
    # -------------------------------------------------------------------
    # Collect unique (filename, page_number) pairs from metadata
    seen = set()
    citation_lines = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        filename = meta.get("filename")
        page = meta.get("page_number")
        if filename is None or page is None:
            continue
        key = (filename, page)
        if key in seen:
            continue
        seen.add(key)
        citation_lines.append(f"- {filename} (page {page})")
    if citation_lines:
        citation_block = "\n**Sources:**\n" + "\n".join(citation_lines)
        answer_text = f"{answer_text}{citation_block}"
    return answer_text
    """Perform RAG: retrieve chunks and generate answer via Gemini.
    If no relevant chunks are found, returns a clear not‑found message.
    """
    # Ensure Gemini is configured
    _configure_gemini()
    chunks = retrieve_relevant_chunks(question, top_k=top_k)
    if not chunks:
        return "I could not find relevant notice information."
    # Build context from chunk documents
    context = "\n---\n".join(chunk["document"] for chunk in chunks if chunk.get("document"))
    prompt = (
        "Answer the following question using ONLY the provided context. "
        "If the answer cannot be found in the context, explicitly state that the notice information could not be found. "
        "Do NOT invent dates, deadlines, or any information not present in the context.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    # response.text may be None if error; fallback
    return response.text.strip() if response and getattr(response, 'text', None) else "Unable to generate answer."
