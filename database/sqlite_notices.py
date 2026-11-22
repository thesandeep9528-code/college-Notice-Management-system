import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "notices.db"

def _ensure_db():
    """Create the SQLite DB and notices table if they don't exist."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                department TEXT NOT NULL,
                semester TEXT NOT NULL,
                deadline TEXT,
                uploaded_by INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

def add_notice(
    title: str,
    description: str,
    category: str,
    department: str,
    semester: str,
    deadline: str,
    uploaded_by: int,
    file_path: str,
    status: str = "pending",
) -> int:
    """Insert a new notice and return its id."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO notices (title, description, category, department, semester, deadline, uploaded_by, file_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                description,
                category,
                department,
                semester,
                deadline,
                uploaded_by,
                file_path,
                status,
            ),
        )
        notice_id = cur.lastrowid
        conn.commit()
        return notice_id
    finally:
        conn.close()

def get_notices_by_user(user_id: int):
    """Return a list of notices uploaded by the given user."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, status, file_path FROM notices WHERE uploaded_by = ?",
            (user_id, ),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "title": r[1],
                "status": r[2],
                "file_path": r[3],
            }
            for r in rows
        ]
    finally:
        conn.close()

def delete_notice(notice_id: int, user_id: int, is_admin: bool = False) -> bool:
    """Delete a notice if the user owns it or is admin. Returns True on success."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        # Verify ownership or admin
        cur.execute(
            "SELECT uploaded_by FROM notices WHERE id = ?",
            (notice_id, ),
        )
        row = cur.fetchone()
        if not row:
            return False
        owner_id = row[0]
        if not (is_admin or owner_id == user_id):
            return False
        # Delete the record
        cur.execute("DELETE FROM notices WHERE id = ?", (notice_id, ))
        conn.commit()
        return True
    finally:
        conn.close()
