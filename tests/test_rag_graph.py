from pathlib import Path
from types import SimpleNamespace

import pytest
from openai import OpenAIError

from backend.services import rag_graph, rag_index


@pytest.fixture(autouse=True)
def clear_compiled_graph():
    rag_graph._compiled_graph.cache_clear()
    yield
    rag_graph._compiled_graph.cache_clear()


def test_question_analysis_uses_prior_user_questions_only():
    result = rag_graph.analyze_question(
        {
            "question": "When does it open?",
            "history": [
                {"role": "user", "content": "Tell me about registration."},
                {"role": "assistant", "content": "It opens soon."},
            ],
        }
    )

    assert result == {
        "retrieval_query": "Tell me about registration. When does it open?",
        "retry_count": 0,
    }


def test_answer_evaluation_requires_a_valid_grounded_source():
    source = {
        "excerpt": "Registration opens on September 12.",
    }
    state = {
        "question": "When does registration open?",
        "retrieval_query": "When does registration open?",
        "sources": [source],
        "answer": "Registration opens on September 12 [Source 1].",
        "generation_mode": "openai",
    }

    assert rag_graph.evaluate_answer(state)["grounded"] is True
    assert rag_graph.evaluate_answer(
        {
            **state,
            "answer": "Registration opens on September 12 [Source 1, page 2].",
        }
    )["grounded"] is True
    uncited = rag_graph.evaluate_answer(
        {**state, "answer": "Registration opens on September 12."}
    )
    assert uncited == {
        "grounded": True,
        "answer": "Registration opens on September 12. [Source 1]",
    }
    assert rag_graph.evaluate_answer(
        {**state, "answer": "Registration opens on September 12 [Source 2]."}
    )["grounded"] is False
    assert rag_graph.evaluate_answer(
        {**state, "answer": "Registration opens on October 5 [Source 1]."}
    )["grounded"] is False
    assert rag_graph.evaluate_answer(
        {
            **state,
            "sources": [source, source.copy()],
            "answer": "Registration opens on September 12.",
        }
    )["grounded"] is False


def test_retry_routing_has_a_fixed_attempt_limit():
    assert rag_graph.route_after_evaluation(
        {"grounded": True, "retry_count": 1}
    ) == "done"
    assert rag_graph.route_after_evaluation(
        {"grounded": False, "retry_count": 1}
    ) == "retry"
    assert rag_graph.route_after_evaluation(
        {"grounded": False, "retry_count": 2}
    ) == "fallback"


def test_graph_retries_once_then_returns_not_found(monkeypatch):
    retrieval_calls = []
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        rag_graph,
        "get_notices_by_status",
        lambda status: retrieval_calls.append(status) or [],
    )

    result = rag_graph.answer_question("When does registration open?")

    assert retrieval_calls == ["approved", "approved"]
    assert result == {
        "answer": rag_graph.NOT_FOUND_ANSWER,
        "sources": [],
    }


def test_generation_failure_returns_source_excerpts(monkeypatch):
    class FailedCompletions:
        def create(self, **kwargs):
            raise OpenAIError("temporary provider failure")

    class FailedOpenAI:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(completions=FailedCompletions())

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(rag_graph, "OpenAI", FailedOpenAI)

    result = rag_graph.generate_answer(
        {
            "question": "When does registration open?",
            "sources": [{"excerpt": "Registration opens September 12."}],
            "context": "[Source 1: Registration, page 2]\nRegistration opens September 12.",
        }
    )

    assert result["generation_mode"] == "excerpts"
    assert "September 12" in result["answer"]


def test_graph_generates_answer_from_approved_chroma_sources(monkeypatch):
    notice = {
        "id": 17,
        "title": "Registration schedule",
        "file_name": "registration.pdf",
        "file_path": "stored.pdf",
    }
    hits = [
        {
            "id": "sqlite_17_2_0",
            "document": "Registration opens on September 12.",
            "metadata": {
                "notice_id": 17,
                "page_number": 2,
                "source": "sqlite_approved",
            },
            "distance": 0.1,
        },
        {
            "id": "sqlite_99_1_0",
            "document": "Pending notice says registration opens October 5.",
            "metadata": {
                "notice_id": 99,
                "page_number": 1,
                "source": "sqlite_approved",
            },
            "distance": 0.0,
        },
    ]

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["max_tokens"] == 160
            assert "[Source 1: Registration schedule, page 2]" in kwargs["messages"][1]["content"]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="Registration opens on September 12 [Source 1, page 2]."
                        )
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(rag_graph, "get_notices_by_status", lambda status: [notice])
    monkeypatch.setattr(rag_graph, "get_chroma_collection", lambda: object())
    monkeypatch.setattr(rag_graph, "sync_approved_notices", lambda notices, collection: True)
    monkeypatch.setattr(rag_graph, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(
        rag_graph,
        "_pdf_path",
        lambda file_path: Path("stored.pdf"),
    )

    def search(query, top_k, where):
        assert where == {
            "$and": [
                {"notice_id": {"$in": [17]}},
                {"source": "sqlite_approved"},
            ]
        }
        return hits

    monkeypatch.setattr(
        rag_graph,
        "_search_similar",
        search,
    )

    result = rag_graph.answer_question("When does registration open?")

    assert "September 12" in result["answer"]
    assert result["sources"] == [
        {
            "notice_id": 17,
            "title": "Registration schedule",
            "file_name": "registration.pdf",
            "page_number": 2,
            "has_file": True,
            "excerpt": "Registration opens on September 12.",
        }
    ]


def test_selected_notice_limits_chroma_sync_and_retrieval(monkeypatch):
    notices = [
        {"id": 17, "title": "Registration schedule"},
        {"id": 18, "title": "Library hours"},
    ]
    indexed = []
    search_filters = []
    monkeypatch.setattr(rag_graph, "get_notices_by_status", lambda status: notices)
    monkeypatch.setattr(rag_graph, "get_chroma_collection", lambda: object())
    monkeypatch.setattr(
        rag_graph,
        "sync_approved_notices",
        lambda scoped_notices, collection: indexed.extend(scoped_notices) or True,
    )
    monkeypatch.setattr(rag_graph, "_pdf_path", lambda file_path: None)

    def search(query, top_k, where):
        search_filters.append(where)
        return [
            {
                "document": "Registration closes on September 12.",
                "metadata": {
                    "notice_id": 17,
                    "page_number": 1,
                    "source": "sqlite_approved",
                },
            },
            {
                "document": "Library closes at 8 PM.",
                "metadata": {
                    "notice_id": 18,
                    "page_number": 1,
                    "source": "sqlite_approved",
                },
            },
        ]

    monkeypatch.setattr(rag_graph, "_search_similar", search)
    result = rag_graph.retrieve_documents(
        {
            "question": "When does registration close?",
            "retrieval_query": "When does registration close?",
            "notice_id": 17,
            "top_k": 5,
            "retry_count": 0,
        }
    )

    assert indexed == [notices[0]]
    assert search_filters[0]["$and"][0] == {"notice_id": {"$in": [17]}}
    assert {source["notice_id"] for source in result["sources"]} == {17}


def test_chroma_search_uses_supported_include_fields(monkeypatch):
    from services import notice_embedding

    class FakeCollection:
        def query(self, **kwargs):
            assert kwargs["include"] == ["documents", "metadatas", "distances"]
            return {
                "ids": [["chunk-1"]],
                "documents": [["Academic calendar for session 2026-27."]],
                "metadatas": [[{"notice_id": 17, "page_number": 1}]],
                "distances": [[0.1]],
            }

    monkeypatch.setattr(notice_embedding, "collection", FakeCollection())

    assert notice_embedding.search_similar("academic calendar") == [
        {
            "id": "chunk-1",
            "document": "Academic calendar for session 2026-27.",
            "metadata": {"notice_id": 17, "page_number": 1},
            "distance": 0.1,
        }
    ]


def test_sync_indexes_approved_pdf_pages_once(monkeypatch, tmp_path):
    class FakeCollection:
        def __init__(self):
            self.records = {}
            self.add_calls = 0

        def get(self, where, include):
            matches = {
                record_id: record
                for record_id, record in self.records.items()
                if self._matches_where(record["metadata"], where)
            }
            return {
                "ids": list(matches),
                "metadatas": [record["metadata"] for record in matches.values()],
            }

        def delete(self, ids):
            for record_id in ids:
                self.records.pop(record_id, None)

        def add(self, ids, documents, metadatas):
            self.add_calls += 1
            self.records.update(
                {
                    record_id: {"document": document, "metadata": metadata}
                    for record_id, document, metadata in zip(ids, documents, metadatas)
                }
            )

        @classmethod
        def _matches_where(cls, metadata, where):
            if "$and" in where:
                return all(cls._matches_where(metadata, item) for item in where["$and"])
            return all(
                metadata.get(key) in value["$in"]
                if isinstance(value, dict) and "$in" in value
                else metadata.get(key) == value
                for key, value in where.items()
            )

    pdf_path = tmp_path / "registration.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(rag_index, "_pdf_path", lambda file_path: pdf_path)
    monkeypatch.setattr(
        rag_index,
        "_extract_pdf_pages",
        lambda file_path, modified_time: ((2, "Registration opens September 12."),),
    )
    notice = {
        "id": 21,
        "title": "Registration",
        "description": "Registration schedule",
        "file_path": "stored.pdf",
        "file_name": "registration.pdf",
    }
    collection = FakeCollection()

    assert rag_index.sync_approved_notices([notice], collection)
    assert any(
        record["metadata"]["page_number"] == 2
        and record["metadata"]["source"] == rag_index.INDEX_SOURCE
        for record in collection.records.values()
    )
    assert rag_index.sync_approved_notices([notice], collection)
    assert collection.add_calls == 1
