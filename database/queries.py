import os
import psycopg2
from .connection import get_connection
from .auth import hash_password, verify_password

# -------------------------------------------------------------------
# User management functions
# -------------------------------------------------------------------

def add_user(email: str, password: str, role: str) -> int:
    """Create a new user and return its generated id.

    The password is hashed before storage using the same PBKDF2 utility.
    """
    pwd_hash = hash_password(password)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (email, pwd_hash, role),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    finally:
        conn.close()


def get_user_by_email(email: str):
    """Return a user row (as a dict) for the given email or ``None``.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()

# -------------------------------------------------------------------
# Notice management functions
# -------------------------------------------------------------------

def add_notice(
    title: str,
    description: str = "",
    category: str = "",
    department: str = "",
    semester: str = "",
    uploaded_by: int = None,
    file_path: str = "",
    status: str = "pending",
    deadline: str = None,
) -> int:
    """Insert a new notice record and return its id.

    ``deadline`` is optional – if supplied it should be an ISO‑8601 string that
    PostgreSQL can cast to ``timestamp with time zone``. The column currently does
    not exist; the migration logic adds it if missing (see ``database/migrate.py``).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notices (title, description, category, department, semester,
                                     uploaded_by, file_path, status, deadline)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    title,
                    description,
                    category,
                    department,
                    semester,
                    uploaded_by,
                    file_path,
                    status,
                    deadline,
                ),
            )
            notice_id = cur.fetchone()[0]
        conn.commit()
        return notice_id
    finally:
        conn.close()


def get_notices_by_status(status: str):
    """Return a list of notice dicts filtered by ``status``.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM notices WHERE status = %s ORDER BY created_at DESC;", (status,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


def update_notice_status(notice_id: int, new_status: str) -> None:
    """Set the ``status`` of a notice.

    ``new_status`` must be one of ``pending``, ``approved`` or ``rejected``.
    """
    if new_status not in {"pending", "approved", "rejected"}:
        raise ValueError(f"Invalid status: {new_status}")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notices SET status = %s WHERE id = %s;
                """,
                (new_status, notice_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_notices_by_user(user_id: int):
    """Return notices uploaded by a specific user.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM notices WHERE uploaded_by = %s ORDER BY created_at DESC;", (user_id,)
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()
