def answer_question(question: str, top_k: int = 5) -> str:
    """Placeholder RAG answer.
    In a full implementation this would query a vector store or LLM.
    For now we return a simple echo.
    """
    return f"You asked: {question}. (This is a placeholder answer.)"
