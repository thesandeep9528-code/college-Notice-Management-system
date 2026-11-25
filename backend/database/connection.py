import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'ai_notice.db')


def get_connection():
    """Return a new SQLite connection to the application database."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _add_column_if_missing(conn, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    """Create or safely extend the local schema without deleting existing data."""
    conn = get_connection()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL DEFAULT '',
                department TEXT NOT NULL DEFAULT '',
                semester TEXT NOT NULL DEFAULT ''
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                department TEXT,
                semester TEXT,
                file_path TEXT,
                uploaded_by INTEGER,
                status TEXT NOT NULL,
                deadline TEXT,
                rejection_reason TEXT,
                file_name TEXT,
                file_size INTEGER,
                created_at TEXT,
                FOREIGN KEY (uploaded_by) REFERENCES users(id)
            )
        ''')

        _add_column_if_missing(conn, "users", "active", "INTEGER NOT NULL DEFAULT 1")
        _add_column_if_missing(conn, "users", "name", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "users", "department", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "users", "semester", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "notices", "deadline", "TEXT")
        _add_column_if_missing(conn, "notices", "rejection_reason", "TEXT")
        _add_column_if_missing(conn, "notices", "file_name", "TEXT")
        _add_column_if_missing(conn, "notices", "file_size", "INTEGER")
        _add_column_if_missing(conn, "notices", "created_at", "TEXT")
        conn.execute(
            "UPDATE notices SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
        )
        conn.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                details TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_notices_status_created "
            "ON notices(status, created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_notices_uploader "
            "ON notices(uploaded_by, status)"
        )
        conn.commit()
    finally:
        conn.close()
