import sqlite3
from .connection import get_connection
from .auth import hash_password, verify_password

def add_user(email: str, password: str, role: str, active: bool = True) -> int:
    conn = get_connection()
    cur = conn.cursor()
    pwd_hash = hash_password(password)
    cur.execute(
        "INSERT INTO users (email, password_hash, role, active) VALUES (?,?,?,?)",
        (email, pwd_hash, role, int(active)),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id

def get_user_by_email(email: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, password_hash, role, active FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "email": row[1], "password_hash": row[2], "role": row[3], "active": bool(row[4])}
    return None

def get_notices_by_status(status: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM notices WHERE status = ?", (status,))
    cols = [description[0] for description in cur.description]
    notices = [dict(zip(cols, row)) for row in cur.fetchall()]
    conn.close()
    return notices

def add_notice(title, description=None, category=None, department=None, semester=None, file_path="/tmp/placeholder.pdf", uploaded_by=None, status="pending"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO notices (title, description, category, department, semester, file_path, uploaded_by, status) VALUES (?,?,?,?,?,?,?,?)",
        (title, description, category, department, semester, file_path, uploaded_by, status),
    )
    notice_id = cur.lastrowid
    conn.commit()
    conn.close()
    return notice_id

def update_notice_status(notice_id: int, status: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notices SET status = ? WHERE id = ?", (status, notice_id))
    conn.commit()
    conn.close()

def count_users_by_role(role: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE role = ?", (role,))
    count = cur.fetchone()[0]
    conn.close()
    return count

def set_user_active(user_id: int, active: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET active = ? WHERE id = ?", (int(active), user_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, role, active FROM users")
    cols = [description[0] for description in cur.description]
    users = [dict(zip(cols, row)) for row in cur.fetchall()]
    conn.close()
    return users

def delete_notice(notice_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
    conn.commit()
    conn.close()
