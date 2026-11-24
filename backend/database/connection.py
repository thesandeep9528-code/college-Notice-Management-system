import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'ai_notice.db')

def get_connection():
    """Return a new SQLite connection to the database file."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Create tables if they don't exist and seed an admin user."""
    conn = get_connection()
    cur = conn.cursor()
    # Users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )
    ''')
    # Notices table (simplified)
    cur.execute('''
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
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        )
    ''')
    conn.commit()
    # Seed default admin if not present (password is plain for demo; real app should hash)
    cur.execute('SELECT 1 FROM users WHERE email = ?', ('admin@example.com',))
    if not cur.fetchone():
        # Use the project's password hashing function later; here store plain for simplicity
        from .auth import hash_password
        admin_hash = hash_password('admin123')
        cur.execute(
            'INSERT INTO users (email, password_hash, role, active) VALUES (?,?,?,?)',
            ('admin@example.com', admin_hash, 'admin', 1)
        )
        conn.commit()
    conn.close()
