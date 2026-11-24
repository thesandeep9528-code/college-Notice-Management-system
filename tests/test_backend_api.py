import asyncio
import hashlib

import httpx
import pytest

from backend.database import connection
from backend.database.connection import db_session
from backend.main import app


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


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", str(tmp_path / "api-tests.sqlite3"))
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
