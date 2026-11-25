import asyncio
import hashlib

import httpx
import pytest

from backend import main, provision_faculty
from backend.database import connection
from backend.database.connection import db_session
from backend.database.queries import (
    add_notice,
    add_user,
    get_notice_by_id,
    get_user_by_email,
    get_user_by_id,
    update_notice_status,
)

app = main.app


class ASGISyncClient:
    def request(self, method, path, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", str(tmp_path / "api-tests.sqlite3"))
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(main, "NOTICE_UPLOAD_DIR", upload_dir)
    monkeypatch.setenv("NOTICE_UPLOAD_DIR", str(upload_dir))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    connection.init_db()
    add_user(
        "faculty@example.edu",
        "secure-pass-123",
        "faculty",
        name="Faculty",
        department="Computer Science",
    )
    add_user(
        "student@example.edu",
        "secure-pass-123",
        "student",
        name="Student",
        department="Computer Science",
        semester="3",
    )
    yield ASGISyncClient()


def _login(client, email="student@example.edu", password="secure-pass-123"):
    response = client.post(
        "/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_user(role, email):
    user_id = add_user(
        email,
        "secure-pass-123",
        role,
        name=email.split("@")[0],
    )
    return get_user_by_id(user_id)


def _make_text_pdf(text):
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    parts = [b"%PDF-1.4\n"]
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(sum(map(len, parts)))
        parts.append(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_offset = sum(map(len, parts))
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    xref += b"".join(
        f"{offset:010d} 00000 n \n".encode() for offset in offsets
    )
    parts.append(
        xref
        + b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode()
        + b"\n%%EOF\n"
    )
    return b"".join(parts)


def test_student_registration_is_scoped_and_authentication_is_signed(client):
    assert client.get("/notices").status_code == 401
    assert client.post(
        "/register",
        json={
            "email": "new-student@example.edu",
            "password": "secure-pass-123",
            "name": "New Student",
            "role": "faculty",
        },
    ).status_code == 422

    registered = client.post(
        "/register",
        json={
            "email": " New-Student@example.edu ",
            "password": "secure-pass-123",
            "name": " New Student ",
            "department": "Computer Science",
            "semester": "2",
        },
    )
    assert registered.status_code == 201
    assert registered.json()["role"] == "student"
    assert registered.json()["name"] == "New Student"
    assert "password_hash" not in registered.json()
    assert client.post(
        "/register",
        json={
            "email": "new-student@example.edu",
            "password": "secure-pass-123",
            "name": "Duplicate Student",
        },
    ).status_code == 409

    headers = _login(client, "new-student@example.edu")
    token = headers["Authorization"].removeprefix("Bearer ")
    assert client.get("/me", headers=headers).json()["role"] == "student"
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert client.get(
        "/me",
        headers={"Authorization": f"Bearer {tampered}"},
    ).status_code == 401
    assert client.get("/faculty/dashboard", headers=headers).status_code == 403


def test_admin_access_is_removed_without_deleting_existing_records(client):
    former_admin_id = add_user(
        "former-admin@example.edu",
        "secure-pass-123",
        "admin",
        name="Former Admin",
    )
    assert get_user_by_email("admin@example.com") is None
    assert client.post(
        "/login",
        json={"email": "former-admin@example.edu", "password": "secure-pass-123"},
    ).status_code == 403
    connection.init_db()

    former_token = main.create_token(former_admin_id)
    assert client.get(
        "/me",
        headers={"Authorization": f"Bearer {former_token}"},
    ).status_code == 403
    assert get_user_by_id(former_admin_id)["role"] == "admin"

    assert client.get("/admin/dashboard").status_code == 404
    assert client.get("/users").status_code == 404
    assert client.post("/users", json={}).status_code == 404
    assert client.put("/notices/1/status", json={"status": "approved"}).status_code == 404


def test_faculty_notices_publish_immediately_and_remain_owner_scoped(client):
    faculty_headers = _login(client, "faculty@example.edu")
    other_faculty = _create_user("faculty", "other@example.edu")
    other_headers = _login(client, other_faculty["email"])
    student_headers = _login(client)

    created = client.post(
        "/notices",
        headers=faculty_headers,
        json={
            "title": "Faculty notice",
            "category": "Academic",
            "department": "Computer Science",
            "uploaded_by": other_faculty["id"],
            "status": "rejected",
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "approved"
    notice_id = created.json()["id"]
    notice = get_notice_by_id(notice_id)
    assert notice["uploaded_by"] != other_faculty["id"]
    assert notice["status"] == "approved"

    student_notices = client.get("/notices", headers=student_headers).json()
    assert [item["id"] for item in student_notices] == [notice_id]
    assert client.get(
        f"/notices/{notice_id}",
        headers=other_headers,
    ).status_code == 404
    assert client.get("/notices", headers=other_headers).json() == []
    pending_filter = client.get(
        "/notices",
        headers=student_headers,
        params={"status": "pending"},
    ).json()
    assert len(pending_filter) == 1
    assert pending_filter[0]["id"] == notice_id

    dashboard = client.get("/faculty/dashboard", headers=faculty_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["approved"] == 1
    assert dashboard.json()["pending"] == 0
    assert client.post(
        "/notices",
        headers=student_headers,
        json={"title": "Student attempt"},
    ).status_code == 403
    assert client.put(
        f"/notices/{notice_id}/status",
        headers=faculty_headers,
        json={"status": "rejected"},
    ).status_code == 404


def test_faculty_pdf_upload_is_immediately_visible_to_students(client, monkeypatch):
    faculty_headers = _login(client, "faculty@example.edu")
    other_faculty = _create_user("faculty", "other@example.edu")
    other_headers = _login(client, other_faculty["email"])
    student_headers = _login(client)
    pdf_content = b"%PDF-1.4\nsample notice"

    uploaded = client.post(
        "/notices/upload",
        headers=faculty_headers,
        data={
            "title": "PDF notice",
            "description": "Review the attached schedule.",
            "category": "Academic",
            "department": "Computer Science",
            "semester": "3",
            "deadline": "2026-12-01",
        },
        files={"pdf": ("schedule.pdf", pdf_content, "application/pdf")},
    )
    assert uploaded.status_code == 201
    notice = uploaded.json()
    assert notice["status"] == "approved"
    assert notice["has_file"] is True
    assert notice["file_name"] == "schedule.pdf"
    assert "file_path" not in notice

    dashboard = client.get("/faculty/dashboard", headers=faculty_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total"] == 1
    assert dashboard.json()["approved"] == 1

    file_response = client.get(
        f"/notices/{notice['id']}/file",
        headers=faculty_headers,
    )
    assert file_response.status_code == 200
    assert file_response.content == pdf_content
    assert file_response.headers["content-type"] == "application/pdf"
    assert client.get(
        f"/notices/{notice['id']}/file",
        headers=other_headers,
    ).status_code == 404
    assert client.get(
        f"/notices/{notice['id']}/file",
        headers=student_headers,
    ).content == pdf_content
    monkeypatch.setattr(
        main,
        "render_pdf_page",
        lambda file_path, page_number: (b"\x89PNG\r\n\x1a\npreview", 1),
    )
    preview = client.get(
        f"/notices/{notice['id']}/pages/1",
        headers=student_headers,
    )
    assert preview.status_code == 200
    assert preview.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert preview.headers["content-type"] == "image/png"
    assert preview.headers["x-pdf-page-count"] == "1"
    assert client.get(
        f"/notices/{notice['id']}/pages/1",
        headers=other_headers,
    ).status_code == 404


def test_upload_rejects_non_pdf_and_oversized_files(client, monkeypatch):
    faculty_headers = _login(client, "faculty@example.edu")
    bad_file = client.post(
        "/notices/upload",
        headers=faculty_headers,
        data={"title": "Invalid attachment"},
        files={"pdf": ("notice.pdf", b"not a PDF", "application/pdf")},
    )
    assert bad_file.status_code == 415

    invalid_deadline = client.post(
        "/notices/upload",
        headers=faculty_headers,
        data={"title": "Invalid deadline", "deadline": "next week"},
        files={"pdf": ("notice.pdf", b"%PDF-1.4\nvalid enough", "application/pdf")},
    )
    assert invalid_deadline.status_code == 422
    assert not main.NOTICE_UPLOAD_DIR.exists()

    monkeypatch.setattr(main, "MAX_NOTICE_PDF_SIZE", 16)
    oversized_file = client.post(
        "/notices/upload",
        headers=faculty_headers,
        data={"title": "Large attachment"},
        files={"pdf": ("notice.pdf", b"%PDF-" + b"x" * 20, "application/pdf")},
    )
    assert oversized_file.status_code == 413
    assert client.get("/notices", headers=faculty_headers).json() == []


def test_faculty_can_update_and_delete_owned_notices_in_any_status(client):
    faculty = get_user_by_email("faculty@example.edu")
    other_faculty = _create_user("faculty", "other@example.edu")
    faculty_headers = _login(client, faculty["email"])
    other_headers = _login(client, other_faculty["email"])

    pending_id = add_notice(
        title="Legacy pending notice",
        uploaded_by=faculty["id"],
        status="pending",
    )
    rejected_id = add_notice(
        title="Legacy rejected notice",
        uploaded_by=faculty["id"],
        status="pending",
    )
    assert update_notice_status(rejected_id, "rejected", "Clarify the date.")

    for notice_id in (pending_id, rejected_id):
        assert client.put(
            f"/notices/{notice_id}/resubmit",
            headers=other_headers,
            data={"title": "Attempt to edit another notice"},
        ).status_code == 404
        updated = client.put(
            f"/notices/{notice_id}/resubmit",
            headers=faculty_headers,
            data={"title": f"Updated notice {notice_id}"},
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "approved"
        assert updated.json()["rejection_reason"] is None

    published = client.post(
        "/notices",
        headers=faculty_headers,
        json={"title": "Published notice"},
    ).json()
    updated = client.put(
        f"/notices/{published['id']}/resubmit",
        headers=faculty_headers,
        data={"title": "Updated published notice"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "approved"
    assert client.delete(
        f"/notices/{published['id']}/faculty",
        headers=other_headers,
    ).status_code == 404
    assert client.delete(
        f"/notices/{published['id']}/faculty",
        headers=faculty_headers,
    ).status_code == 200


def test_student_notice_sorting_and_assistant_are_scoped(client, monkeypatch):
    faculty_headers = _login(client, "faculty@example.edu")
    student_headers = _login(client)
    first = client.post(
        "/notices",
        headers=faculty_headers,
        json={
            "title": "Registration guide",
            "description": "Registration opens on September 12.",
        },
    ).json()
    second = client.post(
        "/notices",
        headers=faculty_headers,
        json={"title": "Library hours", "description": "The library closes at 8 PM."},
    ).json()
    pending_id = add_notice(
        title="Old pending record",
        uploaded_by=get_user_by_email("faculty@example.edu")["id"],
        status="pending",
    )

    assert client.get(
        "/notices",
        headers=student_headers,
        params={"sort": "oldest"},
    ).json()[0]["id"] == first["id"]
    assert [
        item["id"]
        for item in client.get("/notices", headers=student_headers).json()
    ] == [second["id"], first["id"]]
    assert client.get(
        f"/notices/{pending_id}",
        headers=student_headers,
    ).status_code == 404
    assert client.get(
        "/notices",
        headers=student_headers,
        params={"sort": "random"},
    ).status_code == 422

    requests = []

    def fake_answer(question, top_k, history, notice_id):
        requests.append(notice_id)
        if notice_id == first["id"]:
            return {
                "answer": "Registration opens on September 12 [Source 1].",
                "sources": [{"notice_id": notice_id, "excerpt": "September 12"}],
            }
        return {"answer": "I couldn't find that information.", "sources": []}

    monkeypatch.setattr(main, "answer_question", fake_answer)
    answer = client.post(
        "/rag",
        headers=student_headers,
        json={"question": "When does registration open?", "notice_id": first["id"]},
    )
    assert answer.status_code == 200
    assert "September 12" in answer.json()["answer"]
    assert answer.json()["sources"][0]["notice_id"] == first["id"]
    assert client.post(
        "/rag",
        headers=student_headers,
        json={"question": "When does registration open?", "notice_id": pending_id},
    ).status_code == 404
    assert client.post(
        "/rag",
        headers=faculty_headers,
        json={"question": "When does registration open?", "notice_id": first["id"]},
    ).status_code == 403
    assert requests == [first["id"]]


def test_faculty_provisioning_cli_creates_a_faculty_account(client, monkeypatch):
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "provision_faculty",
            "--email",
            "new-faculty@example.edu",
            "--name",
            "New Faculty",
            "--department",
            "Computer Science",
        ],
    )
    passwords = iter(("secure-pass-123", "secure-pass-123"))
    monkeypatch.setattr(provision_faculty.getpass, "getpass", lambda _: next(passwords))

    provision_faculty.main()

    user = get_user_by_email("new-faculty@example.edu")
    assert user["role"] == "faculty"
    assert user["name"] == "New Faculty"


def test_student_assistant_returns_pdf_page_citations(client, monkeypatch):
    from backend.services import rag_graph

    monkeypatch.setattr(rag_graph, "get_chroma_collection", lambda: None)
    faculty_headers = _login(client, "faculty@example.edu")
    student_headers = _login(client)
    uploaded = client.post(
        "/notices/upload",
        headers=faculty_headers,
        data={"title": "Registration deadline", "description": "See the attached schedule."},
        files={
            "pdf": (
                "registration.pdf",
                _make_text_pdf("Registration opens September 12"),
                "application/pdf",
            )
        },
    )
    assert uploaded.status_code == 201
    notice_id = uploaded.json()["id"]
    assert uploaded.json()["status"] == "approved"

    response = client.post(
        "/rag",
        headers=student_headers,
        json={"question": "When does registration open?", "notice_id": notice_id},
    )
    assert response.status_code == 200
    assert "September 12" in response.json()["answer"]
    assert response.json()["sources"][0]["notice_id"] == notice_id
    assert response.json()["sources"][0]["page_number"] == 1


def test_legacy_password_hash_upgrades_after_login(client):
    legacy_hash = hashlib.sha256("secure-pass-123".encode("utf-8")).hexdigest()
    with db_session() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (legacy_hash, "student@example.edu"),
        )

    assert _login(client)["Authorization"].startswith("Bearer ")
    with db_session() as conn:
        upgraded_hash = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?",
            ("student@example.edu",),
        ).fetchone()["password_hash"]
    assert upgraded_hash.startswith("pbkdf2_sha256$")
