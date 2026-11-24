import asyncio
import hashlib

import httpx
import pytest

from backend.database import connection
from backend.database.connection import db_session
from backend import main

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
    connection.init_db()
    yield ASGISyncClient()


def _login(client, email="admin@example.com", password="admin123"):
    response = client.post(
        "/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_user(client, headers, role, email):
    response = client.post(
        "/users",
        headers=headers,
        json={
            "email": email,
            "password": "secure-pass-123",
            "role": role,
            "name": email.split("@")[0],
        },
    )
    assert response.status_code == 201
    return response.json()


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


def test_admin_routes_require_signed_active_identity(client):
    assert client.get("/admin/dashboard").status_code == 401
    assert client.get("/users").status_code == 401

    headers = _login(client)
    token = headers["Authorization"].removeprefix("Bearer ")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert client.get(
        "/admin/dashboard",
        headers={"Authorization": f"Bearer {tampered}"},
    ).status_code == 401

    faculty = _create_user(client, headers, "faculty", "faculty@example.edu")
    faculty_headers = _login(client, "faculty@example.edu", "secure-pass-123")
    assert client.get("/users", headers=faculty_headers).status_code == 403

    assert client.put(
        f"/users/{faculty['id']}/activate",
        params={"active": "false"},
        headers=headers,
    ).status_code == 200
    assert client.get("/notices", headers=faculty_headers).status_code == 401


def test_faculty_cannot_spoof_notice_owner_or_approval(client):
    admin_headers = _login(client)
    faculty = _create_user(client, admin_headers, "faculty", "faculty@example.edu")
    other_faculty = _create_user(client, admin_headers, "faculty", "other@example.edu")
    faculty_headers = _login(client, "faculty@example.edu", "secure-pass-123")
    other_headers = _login(client, "other@example.edu", "secure-pass-123")

    created = client.post(
        "/notices",
        headers=faculty_headers,
        json={
            "title": "Faculty notice",
            "category": "Academic",
            "department": "Computer Science",
            "uploaded_by": other_faculty["id"],
            "status": "approved",
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending"

    admin_notice = client.get(
        "/notices",
        params={"status": "pending"},
        headers=admin_headers,
    ).json()[0]
    assert admin_notice["uploaded_by"] == faculty["id"]
    matching = client.get(
        "/notices",
        headers=faculty_headers,
        params={
            "search": "Faculty notice",
            "status": "pending",
            "category": "Academic",
            "department": "Computer Science",
        },
    )
    assert [notice["id"] for notice in matching.json()] == [admin_notice["id"]]
    assert client.get("/notices", headers=other_headers).json() == []
    assert client.get(
        f"/notices/{admin_notice['id']}",
        headers=other_headers,
    ).status_code == 404
    assert client.put(
        f"/notices/{admin_notice['id']}/status",
        headers=faculty_headers,
        json={"status": "approved"},
    ).status_code == 403
    assert client.get("/admin/dashboard", headers=faculty_headers).status_code == 403

    student = _create_user(client, admin_headers, "student", "student@example.edu")
    student_headers = _login(client, student["email"], "secure-pass-123")
    assert client.post(
        "/notices",
        headers=student_headers,
        json={"title": "Student attempt"},
    ).status_code == 403
    assert client.get(
        "/notices",
        params={"status": "pending"},
        headers=student_headers,
    ).json() == []
    assert client.get("/users", headers=student_headers).status_code == 403


def test_admin_rejection_reason_and_dashboard_activity(client):
    admin_headers = _login(client)
    _create_user(client, admin_headers, "faculty", "faculty@example.edu")
    faculty_headers = _login(client, "faculty@example.edu", "secure-pass-123")
    created = client.post(
        "/notices",
        headers=faculty_headers,
        json={"title": "Exam schedule", "department": "Computer Science"},
    )
    notice_id = created.json()["id"]

    assert client.put(
        f"/notices/{notice_id}/status",
        headers=admin_headers,
        json={"status": "rejected"},
    ).status_code == 422
    rejected = client.put(
        f"/notices/{notice_id}/status",
        headers=admin_headers,
        json={"status": "rejected", "rejection_reason": "Add the exam date."},
    )
    assert rejected.status_code == 200
    edited = client.put(
        f"/notices/{notice_id}",
        headers=admin_headers,
        json={"title": "Updated exam schedule", "deadline": "2026-12-01"},
    )
    assert edited.status_code == 200

    notice = client.get(
        f"/notices/{notice_id}",
        headers=admin_headers,
    ).json()
    assert notice["title"] == "Updated exam schedule"
    assert notice["deadline"] == "2026-12-01"
    assert notice["rejection_reason"] == "Add the exam date."

    dashboard = client.get("/admin/dashboard", headers=admin_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["notices"]["rejected"] == 1
    assert any(
        item["action"] == "rejected"
        for item in dashboard.json()["recent_activity"]
    )


def test_admin_can_search_users_and_cannot_remove_last_admin(client):
    admin_headers = _login(client)
    _create_user(client, admin_headers, "faculty", "faculty@example.edu")
    found = client.get(
        "/users",
        params={"search": "faculty", "role": "faculty", "active": "true"},
        headers=admin_headers,
    )
    assert found.status_code == 200
    assert [user["email"] for user in found.json()] == ["faculty@example.edu"]
    account_id = found.json()[0]["id"]
    updated = client.put(
        f"/users/{account_id}",
        headers=admin_headers,
        json={"name": "Faculty Name", "department": "Computer Science"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Faculty Name"
    assert "password_hash" not in updated.json()

    response = client.put(
        "/users/1",
        headers=admin_headers,
        json={"active": False},
    )
    assert response.status_code == 409


def test_faculty_uploads_pdf_and_file_access_matches_notice_visibility(client):
    admin_headers = _login(client)
    faculty = _create_user(client, admin_headers, "faculty", "faculty@example.edu")
    other = _create_user(client, admin_headers, "faculty", "other@example.edu")
    faculty_headers = _login(client, faculty["email"], "secure-pass-123")
    other_headers = _login(client, other["email"], "secure-pass-123")
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
    assert notice["status"] == "pending"
    assert notice["has_file"] is True
    assert notice["file_name"] == "schedule.pdf"
    assert "file_path" not in notice

    dashboard = client.get("/faculty/dashboard", headers=faculty_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total"] == 1
    assert dashboard.json()["pending"] == 1
    assert dashboard.json()["recent_notices"][0]["id"] == notice["id"]
    assert client.get("/faculty/dashboard", headers=admin_headers).status_code == 403

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

    student = _create_user(client, admin_headers, "student", "student@example.edu")
    student_headers = _login(client, student["email"], "secure-pass-123")
    assert client.post(
        "/notices/upload",
        headers=student_headers,
        data={"title": "Student upload attempt"},
        files={"pdf": ("notice.pdf", pdf_content, "application/pdf")},
    ).status_code == 403
    assert client.get(
        f"/notices/{notice['id']}/file",
        headers=student_headers,
    ).status_code == 404
    assert client.put(
        f"/notices/{notice['id']}/status",
        headers=admin_headers,
        json={"status": "approved"},
    ).status_code == 200
    assert client.get(
        f"/notices/{notice['id']}/file",
        headers=student_headers,
    ).content == pdf_content


def test_upload_rejects_non_pdf_and_oversized_files(client, monkeypatch):
    admin_headers = _login(client)
    faculty = _create_user(client, admin_headers, "faculty", "faculty@example.edu")
    faculty_headers = _login(client, faculty["email"], "secure-pass-123")
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


def test_faculty_can_resubmit_rejected_and_delete_only_owned_unapproved_notices(client):
    admin_headers = _login(client)
    faculty = _create_user(client, admin_headers, "faculty", "faculty@example.edu")
    other = _create_user(client, admin_headers, "faculty", "other@example.edu")
    faculty_headers = _login(client, faculty["email"], "secure-pass-123")
    other_headers = _login(client, other["email"], "secure-pass-123")
    created = client.post(
        "/notices",
        headers=faculty_headers,
        json={"title": "Needs revision"},
    )
    notice_id = created.json()["id"]
    assert client.put(
        f"/notices/{notice_id}/status",
        headers=admin_headers,
        json={"status": "rejected", "rejection_reason": "Clarify the date."},
    ).status_code == 200
    assert client.put(
        f"/notices/{notice_id}/resubmit",
        headers=other_headers,
        data={"title": "Attempt to edit another notice"},
    ).status_code == 404

    resubmitted = client.put(
        f"/notices/{notice_id}/resubmit",
        headers=faculty_headers,
        data={
            "title": "Updated notice",
            "description": "Corrected date.",
            "category": "Academic",
        },
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "pending"
    assert resubmitted.json()["rejection_reason"] is None

    assert client.put(
        f"/notices/{notice_id}/resubmit",
        headers=faculty_headers,
        data={"title": "Second attempt"},
    ).status_code == 409
    assert client.delete(
        f"/notices/{notice_id}/faculty",
        headers=other_headers,
    ).status_code == 404
    assert client.delete(
        f"/notices/{notice_id}/faculty",
        headers=faculty_headers,
    ).status_code == 200

    approved = client.post(
        "/notices",
        headers=faculty_headers,
        json={"title": "Published notice"},
    ).json()
    assert client.put(
        f"/notices/{approved['id']}/status",
        headers=admin_headers,
        json={"status": "approved"},
    ).status_code == 200
    assert client.delete(
        f"/notices/{approved['id']}/faculty",
        headers=faculty_headers,
    ).status_code == 409


def test_legacy_password_hash_upgrades_after_login(client):
    legacy_hash = hashlib.sha256("admin123".encode("utf-8")).hexdigest()
    with db_session() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (legacy_hash, "admin@example.com"),
        )

    assert _login(client)["Authorization"].startswith("Bearer ")
    with db_session() as conn:
        upgraded_hash = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?",
            ("admin@example.com",),
        ).fetchone()["password_hash"]
    assert upgraded_hash.startswith("pbkdf2_sha256$")


def test_student_notice_sorting_and_local_assistant_sources(client):
    admin_headers = _login(client)
    faculty = _create_user(client, admin_headers, "faculty", "faculty@example.edu")
    student = _create_user(client, admin_headers, "student", "student@example.edu")
    faculty_headers = _login(client, faculty["email"], "secure-pass-123")
    student_headers = _login(client, student["email"], "secure-pass-123")

    published_ids = []
    for title, description in (
        ("Registration guide", "Registration opens on September 12 for all students."),
        ("Library hours", "The library closes at 8 PM during the examination period."),
    ):
        created = client.post(
            "/notices",
            headers=faculty_headers,
            json={"title": title, "description": description},
        ).json()
        published_ids.append(created["id"])
        assert client.put(
            f"/notices/{created['id']}/status",
            headers=admin_headers,
            json={"status": "approved"},
        ).status_code == 200

    pending = client.post(
        "/notices",
        headers=faculty_headers,
        json={
            "title": "Registration review",
            "description": "Unapproved registration information.",
        },
    ).json()
    assert client.get(
        f"/notices/{pending['id']}",
        headers=student_headers,
    ).status_code == 404
    assert client.get(
        "/notices",
        headers=student_headers,
        params={"sort": "oldest"},
    ).json()[0]["id"] == published_ids[0]
    assert [
        notice["id"]
        for notice in client.get(
            "/notices",
            headers=student_headers,
            params={"sort": "newest"},
        ).json()
    ] == list(reversed(published_ids))
    assert client.get(
        "/notices",
        headers=student_headers,
        params={"sort": "random"},
    ).status_code == 422

    response = client.post(
        "/rag",
        headers=student_headers,
        json={
            "question": "When does registration open?",
            "history": [{"role": "user", "content": "Tell me about registration."}],
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert "September 12" in result["answer"]
    assert result["sources"][0]["notice_id"] == published_ids[0]
    assert all(source["notice_id"] != pending["id"] for source in result["sources"])
    assert result["sources"][0]["excerpt"]

    assert client.post(
        "/rag",
        headers=faculty_headers,
        json={"question": "When does registration open?"},
    ).status_code == 403


def test_student_assistant_returns_pdf_page_citations(client):
    admin_headers = _login(client)
    faculty = _create_user(client, admin_headers, "faculty", "faculty@example.edu")
    student = _create_user(client, admin_headers, "student", "student@example.edu")
    faculty_headers = _login(client, faculty["email"], "secure-pass-123")
    student_headers = _login(client, student["email"], "secure-pass-123")

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
    assert client.put(
        f"/notices/{notice_id}/status",
        headers=admin_headers,
        json={"status": "approved"},
    ).status_code == 200

    response = client.post(
        "/rag",
        headers=student_headers,
        json={"question": "When does registration open?"},
    )
    assert response.status_code == 200
    assert "September 12" in response.json()["answer"]
    assert response.json()["sources"][0]["notice_id"] == notice_id
    assert response.json()["sources"][0]["page_number"] == 1
