import pytest
from backend.database import connection
from backend.database.queries import (
    add_user,
    get_user_by_email,
    add_notice,
    get_notices_by_status,
)

@pytest.fixture(scope="function", autouse=True)
def setup_database(tmp_path, monkeypatch):
    """Use a fresh SQLite database for each test."""
    monkeypatch.setattr(connection, "DB_PATH", str(tmp_path / "test.sqlite3"))
    connection.init_db()


def test_add_and_get_user():
    email = "test_user@example.com"
    pwd = "secret123"
    role = "student"
    user_id = add_user(email, pwd, role)
    assert isinstance(user_id, int) and user_id > 0

    fetched = get_user_by_email(email)
    assert fetched is not None
    assert fetched["id"] == user_id
    assert fetched["email"] == email
    assert fetched["role"] == role
    # Password is stored hashed; it should not equal the plain text
    assert fetched["password_hash"] != pwd

def test_add_and_query_notice():
    # First, create a user to be the uploader
    uploader_id = add_user("uploader@example.com", "pwd", "faculty")
    notice_id = add_notice(
        title="Test Notice",
        description="A description",
        category="exam",
        department="CS",
        semester="Fall 2024",
        file_path="/tmp/dummy.pdf",
        uploaded_by=uploader_id,
        status="pending",
    )
    assert isinstance(notice_id, int) and notice_id > 0

    pending = get_notices_by_status("pending")
    assert len(pending) == 1
    n = pending[0]
    assert n["id"] == notice_id
    assert n["title"] == "Test Notice"
    assert n["uploaded_by"] == uploader_id
    assert n["status"] == "pending"

    from backend.database.queries import update_notice_status
    update_notice_status(notice_id, "approved")

    approved = get_notices_by_status("approved")
    assert len(approved) == 1
    assert approved[0]["id"] == notice_id
    assert approved[0]["status"] == "approved"
