import os
import base64
from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Import existing backend helpers
from database.connection import init_db, get_connection
from database.queries import (
    add_user,
    get_user_by_email,
    get_notices_by_status,
    add_notice,
    update_notice_status,
    count_users_by_role,
    set_user_active,
    get_all_users,
    delete_notice,
)
from database.auth import hash_password, verify_password
from services.rag import answer_question

# -------------------------------------------------------------------
# Simple token utilities (NOT production ready)
# -------------------------------------------------------------------
def create_token(email: str, role: str) -> str:
    payload = f"{email}:{role}"
    return base64.urlsafe_b64encode(payload.encode()).decode()

def decode_token(token: str) -> dict:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        email, role = decoded.split(":")
        return {"email": email, "role": role}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(request: Request):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    # Expect token as "Bearer <token>"
    if token.lower().startswith("bearer "):
        token = token[7:]
    return decode_token(token)

def require_role(allowed_roles: List[str]):
    async def role_checker(user=Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker

# -------------------------------------------------------------------
# FastAPI app definition
# -------------------------------------------------------------------
app = FastAPI(title="AI College Notice API")

# Allow the React front‑end to call the API (adjust origin as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Pydantic models for request bodies
# -------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str

class UserCreateRequest(BaseModel):
    email: str
    password: str
    role: str
    active: Optional[bool] = True

class NoticeCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    department: Optional[str] = None
    semester: Optional[str] = None
    file_path: str = "/tmp/placeholder.pdf"
    uploaded_by: int
    status: str = "pending"

class StatusUpdateRequest(BaseModel):
    status: str  # "approved" or "rejected"

class RagRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5

# -------------------------------------------------------------------
# Initialise DB on startup
# -------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    init_db()

# -------------------------------------------------------------------
# Authentication endpoints
# -------------------------------------------------------------------
@app.post("/login")
async def login(data: LoginRequest):
    user = get_user_by_email(data.email)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user["email"], user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}

# -------------------------------------------------------------------
# User management – admin only
# -------------------------------------------------------------------
@app.get("/users", dependencies=[Depends(require_role(["admin"]))])
async def list_users():
    return get_all_users()

@app.post("/users", dependencies=[Depends(require_role(["admin"]))])
async def create_user(payload: UserCreateRequest):
    uid = add_user(payload.email, payload.password, payload.role, active=payload.active)
    return {"id": uid, "email": payload.email, "role": payload.role, "active": payload.active}

@app.put("/users/{user_id}/activate", dependencies=[Depends(require_role(["admin"]))])
async def toggle_user_active(user_id: int, active: bool):
    set_user_active(user_id, active)
    return {"id": user_id, "active": active}

@app.delete("/users/{user_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_user(user_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
        conn.commit()
    finally:
        conn.close()
    return {"deleted": user_id}

# -------------------------------------------------------------------
# Notice endpoints
# -------------------------------------------------------------------
@app.post("/notices", dependencies=[Depends(require_role(["faculty"]))])
async def create_notice(payload: NoticeCreateRequest):
    nid = add_notice(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        department=payload.department,
        semester=payload.semester,
        uploaded_by=payload.uploaded_by,
        file_path=payload.file_path,
        status=payload.status,
    )
    return {"id": nid}

@app.get("/notices")
async def list_notices(status: Optional[str] = None, search: Optional[str] = None, category: Optional[str] = None, department: Optional[str] = None, semester: Optional[str] = None, user=Depends(get_current_user)):
    # Students see only approved notices unless admin/faculty request otherwise
    if user["role"] == "student":
        status = "approved"
    notices = get_notices_by_status(status or "approved")
    # Simple filtering – expand as needed
    if search:
        notices = [n for n in notices if search.lower() in (n.get("title") or "").lower() or search.lower() in (n.get("description") or "").lower()]
    if category:
        notices = [n for n in notices if n.get("category") == category]
    if department:
        notices = [n for n in notices if n.get("department") == department]
    if semester:
        notices = [n for n in notices if n.get("semester") == semester]
    return notices

@app.put("/notices/{notice_id}/status", dependencies=[Depends(require_role(["admin"]))])
async def update_notice_status_endpoint(notice_id: int, payload: StatusUpdateRequest):
    update_notice_status(notice_id, payload.status)
    return {"id": notice_id, "status": payload.status}

@app.delete("/notices/{notice_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_notice_endpoint(notice_id: int):
    delete_notice(notice_id)
    return {"deleted": notice_id}

# -------------------------------------------------------------------
# RAG endpoint – students only
# -------------------------------------------------------------------
@app.post("/rag", dependencies=[Depends(require_role(["student"]))])
async def rag_query(payload: RagRequest):
    answer = answer_question(payload.question, top_k=payload.top_k)
    return {"question": payload.question, "answer": answer}

# -------------------------------------------------------------------
# Basic health check
# -------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}
