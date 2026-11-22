import os
import pytest
from services.notice_embedding import collection, search_similar

@pytest.fixture(scope="function")
def cleanup_test_doc():
    # Ensure any leftover test doc is removed before and after test
    test_id = "test_999_1_0"
    # Delete if exists
    try:
        collection.delete(ids=[test_id])
    except Exception:
        pass
    yield test_id
    # Cleanup after test
    try:
        collection.delete(ids=[test_id])
    except Exception:
        pass

def test_citation_metadata_present(cleanup_test_doc):
    test_id = cleanup_test_doc
    # Add a test document with known metadata
    collection.add(
        ids=[test_id],
        documents=["This is a test notice content for citation metadata."],
        metadatas=[{"notice_id": 999, "page_number": 1, "filename": "test_notice.pdf"}],
    )
    # Perform a search that should retrieve this doc
    results = search_similar("test notice", top_k=1)
    assert len(results) > 0, "No results returned"
    result = results[0]
    metadata = result.get("metadata", {})
    assert metadata.get("filename") == "test_notice.pdf", "Filename metadata missing or incorrect"
    assert metadata.get("page_number") == 1, "Page number metadata missing or incorrect"
