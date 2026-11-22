import os, sqlite3

# Path for the SQLite database storing extracted notice intelligence
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "notice_intel.db")


def get_conn():
    """Return a new SQLite connection."""
    return sqlite3.connect(DB_PATH)


def init_sqlite():
    """Create the notice_intel table if it does not exist."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notice_intel (
            notice_id INTEGER PRIMARY KEY,
            category TEXT,
            summary TEXT,
            deadline TEXT,
            file_hash TEXT UNIQUE,
            processed_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def insert_notice_intel(notice_id: int, category: str, summary: str, deadline: str, file_hash: str):
    """Insert a new intelligence record for a notice.

    ``deadline`` should be an ISO‑8601 string or ``None``.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO notice_intel (notice_id, category, summary, deadline, file_hash, processed_at)
        VALUES (?,?,?,?,?,datetime('now'))
        """,
        (notice_id, category, summary, deadline, file_hash),
    )
    conn.commit()
    conn.close()


def get_notice_intel(notice_id: int):
    """Return the intelligence row for ``notice_id`` as a dict or ``None``."""
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM notice_intel WHERE notice_id = ?", (notice_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def check_duplicate_hash(file_hash: str) -> bool:
    """Return ``True`` if a notice with the same ``file_hash`` already exists."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM notice_intel WHERE file_hash = ?", (file_hash,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def update_notice_intel(notice_id: int, category: str = None, summary: str = None, deadline: str = None):
    """Update metadata fields for a notice. Only non‑None arguments are updated."""
    fields = []
    values = []
    if category is not None:
        fields.append("category = ?")
        values.append(category)
    if summary is not None:
        fields.append("summary = ?")
        values.append(summary)
    if deadline is not None:
        fields.append("deadline = ?")
        values.append(deadline)
    if not fields:
        return
    values.append(notice_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE notice_intel SET {', '.join(fields)} WHERE notice_id = ?", tuple(values))
    conn.commit()
    conn.close()
