import os
from database.connection import init_db
import streamlit as st
from database.queries import add_user, get_user_by_email, add_notice, get_notices_by_status

# Ensure DB tables exist when the app starts
def _setup_db():
    init_db()
    st.success("✅ Database ready")

_setup_db()

st.title("AI College Notice Intelligence System")
st.write("Upload a notice PDF and fill in details to store it in the database.")

# ---------- Simple user selection (hard‑coded demo) ----------
# In a real app you would have an auth layer; here we just pick an existing user.
users = [
    {"id": 1, "email": "student1@example.com", "role": "student"},
    {"id": 2, "email": "faculty1@example.com", "role": "faculty"},
    {"id": 3, "email": "admin1@example.com", "role": "admin"},
]
selected_user = st.selectbox("Select uploader (demo)", options=users, format_func=lambda u: f"{u['email']} ({u['role']})")

# ---------- Notice form ----------
with st.form(key="notice_form"):
    title = st.text_input("Title")
    description = st.text_area("Description")
    category = st.text_input("Category")
    department = st.text_input("Department")
    semester = st.text_input("Semester")
    uploaded_file = st.file_uploader("PDF file", type=["pdf"])
    submit = st.form_submit_button("Save Notice")

    if submit:
        if not title:
            st.error("Title is required")
        elif not uploaded_file:
            st.error("Please upload a PDF file")
        else:
            # Save the uploaded file locally
            upload_dir = os.path.join(os.getcwd(), "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Insert the notice record
            notice_id = add_notice(
                title=title,
                description=description,
                category=category,
                department=department,
                semester=semester,
                uploaded_by=selected_user["id"],
                file_path=file_path,
                status="pending",
            )
            st.success(f"✅ Notice saved with id {notice_id}")

# ---------- Show pending notices ----------
st.subheader("Pending Notices")
pending = get_notices_by_status("pending")
if pending:
    for n in pending:
        st.markdown(f"- **{n['title']}** (by user id {n['uploaded_by']})")
else:
    st.info("No pending notices.")
