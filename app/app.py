import os
import streamlit as st
from database.connection import init_db
from database.queries import (
    add_user,
    get_user_by_email,
    add_notice,
    get_notices_by_status,
)
from database.auth import verify_password
from database.seed_admin import seed_admin

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
    st.subheader("Pending Notices")
    pending = get_notices_by_status("pending")
    if pending:
        for n in pending:
            st.markdown(f"- **{n['title']}** (Dept: {n['department']}, Semester: {n['semester']})")
    else:
        st.info("No pending notices.")

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
