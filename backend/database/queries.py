import sqlite3
from typing import Optional

from .auth import hash_password
from .connection import db_session


USER_FIELDS = {"email", "name", "department", "semester", "role", "active", "password"}
NOTICE_FIELDS = {
    "title",
    "description",
    "category",
    "department",
    "semester",
    "deadline",
    "file_path",
    "file_name",
    "file_size",
}
NOTICE_STATUSES = {"pending", "approved", "rejected"}


def _row_dict(row):
    return dict(row) if row is not None else None


def add_user(
    email: str,
    password: str,
    role: str,
    active: bool = True,
    name: str = "",
    department: str = "",
    semester: str = "",
) -> int:
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (email, password_hash, role, active, name, department, semester)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email.strip().lower(),
                hash_password(password),
                role,
                int(active),
                name.strip(),
                department.strip(),
                semester.strip(),
            ),
        )
        return cur.lastrowid


def get_user_by_email(email: str):
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return _row_dict(row)


def get_user_by_id(user_id: int):
    with db_session() as conn:
        return _row_dict(
            conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        )


def get_all_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    active: Optional[bool] = None,
):
    query = "SELECT id, email, name, department, semester, role, active FROM users"
    conditions = []
    params = []
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append("(name LIKE ? COLLATE NOCASE OR email LIKE ? COLLATE NOCASE "
                          "OR department LIKE ? COLLATE NOCASE)")
        params.extend([pattern, pattern, pattern])
    if role:
        conditions.append("role = ?")
        params.append(role)
    if active is not None:
        conditions.append("active = ?")
        params.append(int(active))
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY role, name COLLATE NOCASE, email COLLATE NOCASE"
    with db_session() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def update_user(user_id: int, updates: dict) -> bool:
    if not updates or not set(updates).issubset(USER_FIELDS):
        raise ValueError("Invalid user fields")

    fields = dict(updates)
    if "email" in fields:
        fields["email"] = fields["email"].strip().lower()
    if "password" in fields:
        fields["password_hash"] = hash_password(fields.pop("password"))
    if "active" in fields:
        fields["active"] = int(fields["active"])
    for field in ("name", "department", "semester"):
        if field in fields:
            fields[field] = fields[field].strip()

    assignments = ", ".join(f"{field} = ?" for field in fields)
    values = list(fields.values()) + [user_id]
    with db_session() as conn:
        cur = conn.execute(
            f"UPDATE users SET {assignments} WHERE id = ?",
            values,
        )
        return cur.rowcount > 0


def delete_user(user_id: int) -> bool:
    with db_session() as conn:
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cur.rowcount > 0


def count_users_by_role(role: str, active_only: bool = False) -> int:
    query = "SELECT COUNT(*) FROM users WHERE role = ?"
    params = [role]
    if active_only:
        query += " AND active = 1"
    with db_session() as conn:
        return conn.execute(query, params).fetchone()[0]


def add_notice(
    title,
    description=None,
    category=None,
    department=None,
    semester=None,
    file_path="",
    uploaded_by=None,
    status="pending",
    deadline=None,
    file_name=None,
    file_size=None,
) -> int:
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO notices (
                title, description, category, department, semester, file_path,
                uploaded_by, status, deadline, file_name, file_size, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                title.strip(),
                description,
                category,
                department,
                semester,
                file_path,
                uploaded_by,
                status,
                deadline,
                file_name,
                file_size,
            ),
        )
        return cur.lastrowid


def get_notices_by_status(
    status: Optional[str] = None,
    uploaded_by: Optional[int] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    department: Optional[str] = None,
    semester: Optional[str] = None,
    sort: str = "newest",
):
    if sort not in {"newest", "oldest"}:
        raise ValueError(f"Invalid notice sort order: {sort}")
    query = "SELECT * FROM notices"
    conditions = []
    params = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if uploaded_by is not None:
        conditions.append("uploaded_by = ?")
        params.append(uploaded_by)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            "(title LIKE ? COLLATE NOCASE OR description LIKE ? COLLATE NOCASE)"
        )
        params.extend([pattern, pattern])
    for field, value in (
        ("category", category),
        ("department", department),
        ("semester", semester),
    ):
        if value:
            conditions.append(f"{field} = ?")
            params.append(value)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    direction = "DESC" if sort == "newest" else "ASC"
    query += f" ORDER BY datetime(created_at) {direction}, id {direction}"
    with db_session() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_notice_by_id(notice_id: int):
    with db_session() as conn:
        return _row_dict(
            conn.execute("SELECT * FROM notices WHERE id = ?", (notice_id,)).fetchone()
        )


def update_notice(notice_id: int, updates: dict) -> bool:
    if not updates or not set(updates).issubset(NOTICE_FIELDS):
        raise ValueError("Invalid notice fields")
    assignments = ", ".join(f"{field} = ?" for field in updates)
    values = list(updates.values()) + [notice_id]
    with db_session() as conn:
        cur = conn.execute(
            f"UPDATE notices SET {assignments} WHERE id = ?",
            values,
        )
        return cur.rowcount > 0


def resubmit_notice(notice_id: int, updates: dict) -> bool:
    if not updates or not set(updates).issubset(NOTICE_FIELDS):
        raise ValueError("Invalid notice fields")
    assignments = ", ".join(f"{field} = ?" for field in updates)
    values = list(updates.values()) + [notice_id]
    with db_session() as conn:
        cur = conn.execute(
            f"""
            UPDATE notices
            SET {assignments}, status = 'pending', rejection_reason = NULL
            WHERE id = ? AND status = 'rejected'
            """,
            values,
        )
        return cur.rowcount > 0


def update_notice_status(
    notice_id: int,
    status: str,
    rejection_reason: Optional[str] = None,
) -> bool:
    if status not in {"approved", "rejected"}:
        raise ValueError(f"Invalid status: {status}")
    with db_session() as conn:
        cur = conn.execute(
            """
            UPDATE notices
            SET status = ?, rejection_reason = ?
            WHERE id = ? AND status = 'pending'
            """,
            (status, rejection_reason if status == "rejected" else None, notice_id),
        )
        return cur.rowcount > 0


def set_user_active(user_id: int, active: bool) -> bool:
    with db_session() as conn:
        cur = conn.execute(
            "UPDATE users SET active = ? WHERE id = ?",
            (int(active), user_id),
        )
        return cur.rowcount > 0


def log_activity(
    actor_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    details: str = "",
) -> None:
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO activity_log (actor_id, action, entity_type, entity_id, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (actor_id, action, entity_type, entity_id, details[:500]),
        )


def get_recent_activity(limit: int = 8):
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT activity_log.id, activity_log.action, activity_log.entity_type,
                   activity_log.entity_id, activity_log.details, activity_log.created_at,
                   users.name AS actor_name, users.email AS actor_email
            FROM activity_log
            LEFT JOIN users ON users.id = activity_log.actor_id
            ORDER BY activity_log.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_notice_counts(uploaded_by: Optional[int] = None):
    counts = {status: 0 for status in NOTICE_STATUSES}
    where_clause = " WHERE uploaded_by = ?" if uploaded_by is not None else ""
    params = (uploaded_by,) if uploaded_by is not None else ()
    with db_session() as conn:
        counts["total"] = conn.execute(
            f"SELECT COUNT(*) FROM notices{where_clause}", params
        ).fetchone()[0]
        for row in conn.execute(
            f"SELECT status, COUNT(*) AS count FROM notices{where_clause} GROUP BY status",
            params,
        ):
            if row["status"] in counts:
                counts[row["status"]] = row["count"]
    return counts


def delete_notice(notice_id: int) -> bool:
    with db_session() as conn:
        cur = conn.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
        return cur.rowcount > 0
