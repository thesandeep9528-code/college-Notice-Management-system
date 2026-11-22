import os
import streamlit as st
from datetime import datetime
from database.connection import init_db, get_connection
from database.queries import (
    add_user,
    get_user_by_email,
    add_notice,
    get_notices_by_status,
    update_notice_status,
    count_users_by_role,
    set_user_active,
    get_all_users,
    delete_notice,
)
from database.auth import verify_password
from database.seed_admin import seed_admin

# -------------------------------------------------------------------
# Simple admin activity logger
# -------------------------------------------------------------------
def log_admin_action(action: str, details: str = ""):
    """Append a line to admin activity log stored in logs/admin.log."""
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "admin.log")
    timestamp = datetime.utcnow().isoformat()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} | {action} | {details}\n")
from services.rag import answer_question

# -------------------------------------------------------------------
# Helper: role‑based access control decorator (backend protection)
# -------------------------------------------------------------------
def require_role(allowed_roles):
    """Decorator to protect a function so it only runs for allowed roles.
    Raises an exception if the current session user does not have permission.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if "user" not in st.session_state:
                st.error("You must be logged in to perform this action.")
                st.stop()
            role = st.session_state.user["role"]
            if role not in allowed_roles:
                st.error(f"Access denied for role '{role}'.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator

# -------------------------------------------------------------------
# Initialize DB and ensure at least one admin exists (seed if needed)
# -------------------------------------------------------------------
init_db()
seed_admin()

# -------------------------------------------------------------------
# Session state defaults
# -------------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None

# -------------------------------------------------------------------
# Logout handling
# -------------------------------------------------------------------
if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.experimental_rerun()

# -------------------------------------------------------------------
# Login page (shown when not logged in)
# -------------------------------------------------------------------
if st.session_state.user is None:
    st.title("AI College Notice – Login")
    with st.form(key="login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            user_rec = get_user_by_email(email)
            if user_rec and verify_password(password, user_rec["password_hash"]):
                st.session_state.user = user_rec
                st.success(f"Logged in as {user_rec['role']} ({user_rec['email']})")
                st.experimental_rerun()
            else:
                st.error("Invalid email or password")
    st.stop()

# -------------------------------------------------------------------
# After login – show role‑specific dashboard
# -------------------------------------------------------------------
role = st.session_state.user["role"]
st.title(f"AI College Notice – {role.capitalize()} Dashboard")

# -------------------------------------------------------------------
# Student dashboard – view pending notices only
# -------------------------------------------------------------------
@require_role(["student"])
def student_dashboard():
    st.subheader("Approved Notices")
    # Fetch approved notices
    approved = get_notices_by_status("approved")
    # Search UI
    search_term = st.text_input("Search notices (title/description)")
    categories = sorted({n["category"] for n in approved if n.get("category")})
    selected_category = st.selectbox("Filter by category", ["All"] + categories)
    # Filter logic
    filtered = []
    for n in approved:
        if selected_category != "All" and n.get("category") != selected_category:
            continue
        if search_term:
            if search_term.lower() not in (n.get("title") or "").lower() and \
               search_term.lower() not in (n.get("description") or "").lower():
                continue
        filtered.append(n)
    if not filtered:
        st.info("No notices match the criteria.")
    else:
        for n in filtered:
            st.markdown(f"**{n['title']}** (Dept: {n.get('department','')}, Semester: {n.get('semester','')})")
            if n.get("description"):
                st.caption(n["description"])
            st.write("Category:", n.get("category", "-"))
            st.markdown("---")
    # RAG Q&A
    st.subheader("Ask a question about the notices")
    with st.form(key="question_form"):
        question = st.text_area("Your question")
        submit_q = st.form_submit_button("Get Answer")
        if submit_q and question.strip():
            with st.spinner("Thinking..."):
                answer = answer_question(question)
            st.markdown(f"**Answer:** {answer}")


# -------------------------------------------------------------------
# Faculty dashboard – can create a new notice (upload later)
# -------------------------------------------------------------------
@require_role(["faculty"])
def faculty_dashboard():
    st.subheader("Create a New Notice (PDF upload will be added later)")
    with st.form(key="notice_form"):
        title = st.text_input("Title")
        description = st.text_area("Description")
        category = st.text_input("Category")
        department = st.text_input("Department")
        semester = st.text_input("Semester")
        # No file upload for now – placeholder path
        dummy_path = "/tmp/placeholder.pdf"
        submit = st.form_submit_button("Save Notice")
        if submit:
            if not title:
                st.error("Title is required")
            else:
                notice_id = add_notice(
                    title=title,
                    description=description,
                    category=category,
                    department=department,
                    semester=semester,
                    uploaded_by=st.session_state.user["id"],
                    file_path=dummy_path,
                    status="pending",
                )
                st.success(f"Notice saved with id {notice_id}")

# -------------------------------------------------------------------
# Admin dashboard – view all notices and change status
# -------------------------------------------------------------------
@require_role(["admin"])
def admin_dashboard():
    st.subheader("User Management")
    # Totals
    student_total = count_users_by_role("student")
    faculty_total = count_users_by_role("faculty")
    st.write(f"Total Students: {student_total} | Total Faculty: {faculty_total}")
    # Create new user
    with st.form(key="create_user_form"):
        new_email = st.text_input("New user email")
        new_password = st.text_input("Password", type="password")
        new_role = st.selectbox("Role", ["student", "faculty"])
        new_active = st.checkbox("Active", value=True)
        create_submitted = st.form_submit_button("Create User")
        if create_submitted:
            if not (new_email and new_password):
                st.error("Email and password required")
            else:
                uid = add_user(new_email, new_password, new_role, active=new_active)
                st.success(f"User created with id {uid}")
                log_admin_action("user_created", f"id={uid}, role={new_role}, active={new_active}")
    # List all users
    all_users = get_all_users()
    for u in all_users:
        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.write(f"{u['email']} ({u['role']}) – {'Active' if u.get('active', True) else 'Inactive'}")
        with cols[1]:
            if u['role'] != 'admin':
                if st.button("Toggle Active", key=f"toggle_{u['id']}"):
                    set_user_active(u['id'], not u.get('active', True))
                    st.success("Status updated")
                    log_admin_action("user_toggle_active", f"id={u['id']}, new={not u.get('active', True)}")
                    st.experimental_rerun()
        with cols[2]:
            if u['role'] != 'admin':
                if st.button("Delete", key=f"del_{u['id']}"):
                    conn = get_connection()
                    try:
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM users WHERE id = %s;", (u['id'],))
                        conn.commit()
                    finally:
                        conn.close()
                    st.success("User deleted")
                    log_admin_action("user_deleted", f"id={u['id']}")
                    st.experimental_rerun()
    st.markdown("---")
    st.subheader("Notice Management")
    # Tabs for statuses
    status_tabs = st.tabs(["Pending", "Approved", "Rejected"])
    for tab, status in zip(status_tabs, ["pending", "approved", "rejected"]):
        with tab:
            notices = get_notices_by_status(status)
            for n in notices:
                cols = st.columns([4, 1, 1, 1])
                with cols[0]:
                    st.markdown(f"**{n['title']}** (by {n.get('uploaded_by')})")
                with cols[1]:
                    if n.get('file_path') and os.path.isfile(n['file_path']):
                        if st.button("Preview", key=f"prev_{n['id']}"):
                            with open(n['file_path'], "rb") as f:
                                st.download_button("Download PDF", data=f, file_name=os.path.basename(n['file_path']))
                if status == "pending":
                    with cols[2]:
                        if st.button("Approve", key=f"ap_{n['id']}"):
                            update_notice_status(n['id'], "approved")
                            # Immediately process for vector DB
                            process_approved_notices()
                            st.success("Approved")
                            log_admin_action("notice_approved", f"id={n['id']}")
                            st.experimental_rerun()
                    with cols[3]:
                        if st.button("Reject", key=f"re_{n['id']}"):
                            update_notice_status(n['id'], "rejected")
                            st.success("Rejected")
                            log_admin_action("notice_rejected", f"id={n['id']}")
                            st.experimental_rerun()
                else:
                    # For approved/rejected just show status, maybe allow delete
                    with cols[2]:
                        if st.button("Delete", key=f"del_{n['id']}"):
                            delete_notice(n['id'])
                            st.success("Notice deleted")
                            log_admin_action("notice_deleted", f"id={n['id']}")
                            st.experimental_rerun()

def admin_dashboard():
    st.subheader("All Notices")
    # Fetch all notices regardless of status
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM notices ORDER BY created_at DESC;")
            all_notices = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    for n in all_notices:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{n['title']}** (Status: {n['status']})")
        with col2:
            if n['status'] == 'pending':
                if st.button(f"Approve {n['id']}", key=f"ap_{n['id']}"):
                    update_notice_status(n['id'], 'approved')
                    st.success(f"Notice {n['id']} approved")
                    st.experimental_rerun()
                if st.button(f"Reject {n['id']}", key=f"re_{n['id']}"):
                    update_notice_status(n['id'], 'rejected')
                    st.success(f"Notice {n['id']} rejected")
                    st.experimental_rerun()
    st.subheader("All Notices")
    all_notices = get_notices_by_status("pending") + get_notices_by_status("approved") + get_notices_by_status("rejected")
    for n in all_notices:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{n['title']}** (Status: {n['status']})")
        with col2:
            # Simple status change buttons (demo only)
            if n['status'] == 'pending':
                if st.button(f"Approve {n['id']}", key=f"ap_{n['id']}"):
                    # Direct DB update (protected backend)
                    conn = get_connection()
                    try:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE notices SET status='approved' WHERE id=%s;", (n['id'],))
                        conn.commit()
                    finally:
                        conn.close()
                    st.success(f"Notice {n['id']} approved")
                    st.experimental_rerun()
                if st.button(f"Reject {n['id']}", key=f"re_{n['id']}"):
                    conn = get_connection()
                    try:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE notices SET status='rejected' WHERE id=%s;", (n['id'],))
                        conn.commit()
                    finally:
                        conn.close()
                    st.success(f"Notice {n['id']} rejected")
                    st.experimental_rerun()

# -------------------------------------------------------------------
# Route to the correct dashboard based on role
# -------------------------------------------------------------------
if role == "student":
    student_dashboard()
elif role == "faculty":
    faculty_dashboard()
elif role == "admin":
    admin_dashboard()
else:
    st.error("Unknown role – cannot display dashboard.")
