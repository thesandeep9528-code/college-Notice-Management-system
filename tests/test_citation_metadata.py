from services import notice_embedding


def test_citation_metadata_present(monkeypatch):
    expected_metadata = {
        "notice_id": 999,
        "page_number": 1,
        "filename": "test_notice.pdf",
    }

    class FakeCollection:
        def query(self, query_texts, n_results, include, where=None):
            return {
                "ids": [["test_999_1_0"]],
                "documents": [["This is a test notice content for citation metadata."]],
                "metadatas": [[expected_metadata]],
                "distances": [[0.0]],
            }

    monkeypatch.setattr(notice_embedding, "collection", FakeCollection())
    results = notice_embedding.search_similar("test notice", top_k=1)

    assert len(results) == 1
    assert results[0]["metadata"]["filename"] == "test_notice.pdf"
    assert results[0]["metadata"]["page_number"] == 1


def test_search_similar_applies_current_approval_filter(monkeypatch):
    expected_where = {
        "$and": [
            {"notice_id": {"$in": [12, 14]}},
            {"source": "sqlite_approved"},
        ]
    }

    class FakeCollection:
        def query(self, query_texts, n_results, include, where=None):
            assert where == expected_where
            return {
                "ids": [["sqlite_12_1_0"]],
                "documents": [["Approved notice text"]],
                "metadatas": [[{"notice_id": 12, "page_number": 1}]],
                "distances": [[0.1]],
            }

    monkeypatch.setattr(notice_embedding, "collection", FakeCollection())
    results = notice_embedding.search_similar(
        "approved",
        top_k=2,
        where=expected_where,
    )

    assert results[0]["metadata"]["notice_id"] == 12
