import os
import sqlite3
from contextlib import contextmanager

# Path to the SQLite DB file (stored alongside the backend folder)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "ai_notice.db")

def get_connection():
    """Return a new SQLite connection to the local database file."""
    # Enable row access by name for convenience
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def db_session():
    """Context manager that yields a SQLite connection and commits on success.
    The connection is closed automatically.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Create tables if they don't exist, add missing legacy columns, and seed a default admin.
    Uses db_session to manage the connection and avoid SQLite lock issues.
    """
    with db_session() as conn:
        # Users table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                name TEXT DEFAULT "",
                department TEXT DEFAULT "",
                semester TEXT DEFAULT ""
            );
            """
        )
        # Notices table
        conn.execute(
            """
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
                file_name TEXT,
                file_size INTEGER,
                rejection_reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (uploaded_by) REFERENCES users(id)
            );
            """
        )
        # Add missing columns for legacy users (safety)
        for col in ["name", "department", "semester"]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT ''")
            except Exception:
                pass
        # Ensure existing rows have empty strings for new columns
        conn.execute("UPDATE users SET name = '' WHERE name IS NULL")
        conn.execute("UPDATE users SET department = '' WHERE department IS NULL")
        conn.execute("UPDATE users SET semester = '' WHERE semester IS NULL")
        # Seed default admin if missing
        row = conn.execute("SELECT 1 FROM users WHERE email = ?", ("admin@example.com",)).fetchone()
        if not row:
            from .auth import hash_password
            admin_hash = hash_password("admin123")
            conn.execute(
                "INSERT INTO users (email, password_hash, role, active) VALUES (?,?,?,?)",
                ("admin@example.com", admin_hash, "admin", 1),
            )
        # Add missing columns for legacy notices
        for col, typ in [("deadline", "TEXT"), ("file_name", "TEXT"), ("file_size", "INTEGER"), ("rejection_reason", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE notices ADD COLUMN {col} {typ}")
            except Exception:
                pass
        # Ensure created_at column exists (no effect if already present)
        try:
            conn.execute("ALTER TABLE notices ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")
        except Exception:
            pass
