import os
import pytest
from database.connection import init_db, get_connection
from database.queries import (
    add_user,
    get_user_by_email,
    add_notice,
    get_notices_by_status,
)

# -------------------------------------------------------------------
# Helper to wipe tables between test runs (so tests are idempotent)
# -------------------------------------------------------------------
def _clear_tables():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE notices RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE TABLE users RESTART IDENTITY CASCADE;")
        conn.commit()
    finally:
        conn.close()

# -------------------------------------------------------------------
# Pytest fixtures
# -------------------------------------------------------------------
@pytest.fixture(scope="function", autouse=True)
def setup_and_teardown():
    """Create tables, clear any existing rows, then yield to the test.
    After the test finishes we clean up again.
    """
    init_db()
    _clear_tables()
    yield
    _clear_tables()

# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------
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
        uploaded_by=uploader_id,
        file_path="/tmp/dummy.pdf",
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

    # Change status manually to test filter (simulating an update)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE notices SET status = 'approved' WHERE id = %s;", (notice_id,))
        conn.commit()
    finally:
        conn.close()

    approved = get_notices_by_status("approved")
    assert len(approved) == 1
    assert approved[0]["id"] == notice_id
    assert approved[0]["status"] == "approved"
