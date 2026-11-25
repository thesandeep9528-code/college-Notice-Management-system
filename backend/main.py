import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from dotenv import load_dotenv

from .database.auth import needs_rehash, verify_password
from .database.connection import init_db
from .database.queries import (
    add_notice,
    add_user,
    delete_notice,
    get_notice_by_id,
    get_notice_counts,
    get_notices_by_status,
    get_user_by_email,
    get_user_by_id,
    log_activity,
    resubmit_notice,
    update_user,
)
from .services.rag_graph import answer_question
from services.pdf_service import (
    PDFPageNotFoundError,
    PDFProcessingError,
    render_pdf_page,
)


load_dotenv()
_configured_auth_secret = os.getenv("AUTH_SECRET_KEY")
if _configured_auth_secret:
    AUTH_SECRET_KEY = _configured_auth_secret.encode("utf-8")
    if len(AUTH_SECRET_KEY) < 32:
        raise RuntimeError("AUTH_SECRET_KEY must contain at least 32 bytes")
elif os.getenv("APP_ENV", "development").lower() == "production":
    raise RuntimeError("AUTH_SECRET_KEY must be configured in production")
else:
    AUTH_SECRET_KEY = secrets.token_bytes(32)

TOKEN_TTL_SECONDS = 8 * 60 * 60
USER_ROLES = {"faculty", "student"}
NOTICE_STATUSES = {"pending", "approved", "rejected"}
NOTICE_UPLOAD_DIR = Path(
    os.getenv(
        "NOTICE_UPLOAD_DIR",
        str(Path(__file__).resolve().parent / "uploads" / "notices"),
    )
).resolve()
MAX_NOTICE_PDF_SIZE = 10 * 1024 * 1024


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int) -> str:
    payload = _b64encode(
        json.dumps(
            {"sub": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS},
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signature = hmac.new(
        AUTH_SECRET_KEY, payload.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{payload}.{_b64encode(signature)}"


def decode_token(token: str) -> int:
    try:
        payload, signature = token.split(".", 1)
        expected = _b64encode(
            hmac.new(
                AUTH_SECRET_KEY, payload.encode("ascii"), hashlib.sha256
            ).digest()
        )
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid signature")
        claims = json.loads(_b64decode(payload))
        user_id = claims["sub"]
        expiry = claims["exp"]
        if type(user_id) is not int or type(expiry) is not int or expiry <= time.time():
            raise ValueError("Invalid token claims")
        return user_id
    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        binascii.Error,
    ) as error:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from error


async def get_current_user(request: Request):
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Missing bearer token")

    account = get_user_by_id(decode_token(token.strip()))
    if not account or not account["active"]:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    if account["role"] not in USER_ROLES:
        raise HTTPException(status_code=403, detail="This account role is no longer supported")
    return account


def require_role(allowed_roles: List[str]):
    async def role_checker(user=Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return role_checker


def _public_user(account: dict) -> dict:
    return {
        "id": account["id"],
        "email": account["email"],
        "name": account.get("name", ""),
        "department": account.get("department", ""),
        "semester": account.get("semester", ""),
        "role": account["role"],
        "active": bool(account["active"]),
    }


def _stored_pdf_path(file_path: Optional[str]) -> Optional[Path]:
    if not file_path or Path(file_path).name != file_path or not file_path.lower().endswith(".pdf"):
        return None
    return NOTICE_UPLOAD_DIR / file_path


def _public_notice(notice: dict) -> dict:
    public = {key: value for key, value in notice.items() if key != "file_path"}
    path = _stored_pdf_path(notice.get("file_path"))
    has_file = bool(path and path.is_file())
    public["has_file"] = has_file
    public["file_name"] = notice.get("file_name") if has_file else None
    public["file_size"] = notice.get("file_size") if has_file else None
    return public


async def _store_notice_pdf(upload: UploadFile) -> dict:
    filename = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)[:255]
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Choose a PDF file")
    if upload.content_type not in {None, "application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Only PDF files are supported")

    content = await upload.read(MAX_NOTICE_PDF_SIZE + 1)
    if len(content) > MAX_NOTICE_PDF_SIZE:
        raise HTTPException(status_code=413, detail="PDF must be 10 MiB or smaller")
    if not content or b"%PDF-" not in content[:1024]:
        raise HTTPException(status_code=415, detail="The selected file is not a valid PDF")

    storage_key = f"{uuid.uuid4().hex}.pdf"
    NOTICE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with (NOTICE_UPLOAD_DIR / storage_key).open("xb") as stored_file:
            stored_file.write(content)
    except OSError as error:
        raise HTTPException(status_code=500, detail="Unable to store the PDF file") from error
    return {"file_path": storage_key, "file_name": filename, "file_size": len(content)}


def _delete_notice_pdf(notice: dict) -> None:
    path = _stored_pdf_path(notice.get("file_path"))
    if not path:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise HTTPException(status_code=500, detail="Unable to remove the notice PDF") from error


def _clean_deadline(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Deadline must be a valid YYYY-MM-DD date") from error
    if parsed.isoformat() != value:
        raise ValueError("Deadline must use the YYYY-MM-DD format")
    return parsed.isoformat()


def _validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 255 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(status_code=422, detail="A valid email address is required")
    return normalized


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI College Notice API", lifespan=lifespan)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-PDF-Page-Count"],
)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class StudentRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    department: str = Field(default="", max_length=120)
    semester: str = Field(default="", max_length=20)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value):
        normalized = value.strip()
        if not normalized:
            raise ValueError("A name is required")
        return normalized


class NoticeCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=10_000)
    category: Optional[str] = Field(default=None, max_length=100)
    department: Optional[str] = Field(default=None, max_length=120)
    semester: Optional[str] = Field(default=None, max_length=20)
    deadline: Optional[str] = Field(default=None, max_length=40)

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value):
        return _clean_deadline(value)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value):
        if not value.strip():
            raise ValueError("Chat messages cannot be blank")
        return value.strip()


class RagRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    notice_id: int = Field(ge=1)
    top_k: Optional[int] = Field(default=5, ge=1, le=20)
    history: List[ChatTurn] = Field(default_factory=list, max_length=8)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value):
        if not value.strip():
            raise ValueError("Ask a notice-related question")
        return value.strip()


@app.post("/login")
async def login(data: LoginRequest):
    user = get_user_by_email(data.email)
    if not user or not user["active"] or not verify_password(
        data.password, user["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user["role"] not in USER_ROLES:
        raise HTTPException(status_code=403, detail="This account role is no longer supported")
    if needs_rehash(user["password_hash"]):
        update_user(user["id"], {"password": data.password})
    return {
        "access_token": create_token(user["id"]),
        "token_type": "bearer",
        "role": user["role"],
    }


@app.get("/me")
async def current_user(user=Depends(get_current_user)):
    return _public_user(user)


@app.post("/register", status_code=201)
async def register_student(payload: StudentRegistrationRequest):
    try:
        user_id = add_user(
            email=_validate_email(payload.email),
            password=payload.password,
            role="student",
            name=payload.name.strip(),
            department=payload.department.strip(),
            semester=payload.semester.strip(),
        )
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="Email is already registered") from error
    return _public_user(get_user_by_id(user_id))


@app.get("/faculty/dashboard")
async def faculty_dashboard(user=Depends(require_role(["faculty"]))):
    recent_notices = get_notices_by_status(uploaded_by=user["id"])[:5]
    return {
        **get_notice_counts(uploaded_by=user["id"]),
        "recent_notices": [_public_notice(notice) for notice in recent_notices],
    }


@app.get("/notices")
async def list_notices(
    status: Optional[Literal["pending", "approved", "rejected"]] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    department: Optional[str] = None,
    semester: Optional[str] = None,
    sort: Literal["newest", "oldest"] = "newest",
    user=Depends(get_current_user),
):
    owner_id = None
    if user["role"] == "student":
        status = "approved"
    elif user["role"] == "faculty":
        owner_id = user["id"]
    notices = get_notices_by_status(
        status=status,
        uploaded_by=owner_id,
        search=search,
        category=category,
        department=department,
        semester=semester,
        sort=sort,
    )
    return [_public_notice(notice) for notice in notices]


def _assert_notice_visible(notice: dict, user: dict) -> None:
    if user["role"] == "student" and notice["status"] != "approved":
        raise HTTPException(status_code=404, detail="Notice not found")
    if user["role"] == "faculty" and notice["uploaded_by"] != user["id"]:
        raise HTTPException(status_code=404, detail="Notice not found")


@app.get("/notices/{notice_id}")
async def get_notice(notice_id: int, user=Depends(get_current_user)):
    notice = get_notice_by_id(notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    _assert_notice_visible(notice, user)
    return _public_notice(notice)


@app.get("/notices/{notice_id}/file")
async def get_notice_file(
    notice_id: int,
    download: bool = False,
    user=Depends(get_current_user),
):
    notice = get_notice_by_id(notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    _assert_notice_visible(notice, user)
    file_path = _stored_pdf_path(notice.get("file_path"))
    if not file_path or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Notice PDF not found")
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=notice.get("file_name") or "notice.pdf",
        content_disposition_type="attachment" if download else "inline",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.get("/notices/{notice_id}/pages/{page_number}")
async def get_notice_pdf_page(
    notice_id: int,
    page_number: int,
    user=Depends(get_current_user),
):
    notice = get_notice_by_id(notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    _assert_notice_visible(notice, user)
    file_path = _stored_pdf_path(notice.get("file_path"))
    if not file_path or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Notice PDF not found")

    try:
        image, page_count = render_pdf_page(str(file_path), page_number)
    except PDFPageNotFoundError as error:
        raise HTTPException(status_code=404, detail="PDF page not found") from error
    except PDFProcessingError as error:
        logger.exception("Unable to render notice %s page %s", notice_id, page_number)
        raise HTTPException(
            status_code=422,
            detail="Unable to preview this PDF",
        ) from error

    return Response(
        content=image,
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PDF-Page-Count": str(page_count),
        },
    )


@app.post("/notices", status_code=201)
async def create_notice(
    payload: NoticeCreateRequest,
    user=Depends(require_role(["faculty"])),
):
    if not payload.title.strip():
        raise HTTPException(status_code=422, detail="A notice title is required")
    notice_id = add_notice(
        title=payload.title.strip(),
        description=payload.description,
        category=payload.category,
        department=payload.department,
        semester=payload.semester,
        deadline=payload.deadline,
        uploaded_by=user["id"],
        status="approved",
    )
    log_activity(user["id"], "published", "notice", notice_id, payload.title.strip())
    return {"id": notice_id, "status": "approved"}


@app.post("/notices/upload", status_code=201)
async def upload_notice(
    title: str = Form(..., min_length=1, max_length=255),
    description: Optional[str] = Form(default=None, max_length=10_000),
    category: Optional[str] = Form(default=None, max_length=100),
    department: Optional[str] = Form(default=None, max_length=120),
    semester: Optional[str] = Form(default=None, max_length=20),
    deadline: Optional[str] = Form(default=None, max_length=40),
    pdf: UploadFile = File(...),
    user=Depends(require_role(["faculty"])),
):
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=422, detail="A notice title is required")
    try:
        clean_deadline = _clean_deadline(deadline)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    attachment = await _store_notice_pdf(pdf)
    try:
        notice_id = add_notice(
            title=clean_title,
            description=(description or "").strip() or None,
            category=(category or "").strip() or None,
            department=(department or "").strip() or None,
            semester=(semester or "").strip() or None,
            deadline=clean_deadline,
            uploaded_by=user["id"],
            status="approved",
            **attachment,
        )
    except sqlite3.Error as error:
        _delete_notice_pdf(attachment)
        raise HTTPException(status_code=500, detail="Unable to save the notice") from error
    log_activity(user["id"], "published", "notice", notice_id, clean_title)
    return _public_notice(get_notice_by_id(notice_id))


@app.put("/notices/{notice_id}/resubmit")
async def resubmit_faculty_notice(
    notice_id: int,
    title: str = Form(..., min_length=1, max_length=255),
    description: Optional[str] = Form(default=None, max_length=10_000),
    category: Optional[str] = Form(default=None, max_length=100),
    department: Optional[str] = Form(default=None, max_length=120),
    semester: Optional[str] = Form(default=None, max_length=20),
    deadline: Optional[str] = Form(default=None, max_length=40),
    pdf: Optional[UploadFile] = File(default=None),
    user=Depends(require_role(["faculty"])),
):
    notice = get_notice_by_id(notice_id)
    if not notice or notice["uploaded_by"] != user["id"]:
        raise HTTPException(status_code=404, detail="Notice not found")
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=422, detail="A notice title is required")
    try:
        clean_deadline = _clean_deadline(deadline)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    updates = {
        "title": clean_title,
        "description": (description or "").strip() or None,
        "category": (category or "").strip() or None,
        "department": (department or "").strip() or None,
        "semester": (semester or "").strip() or None,
        "deadline": clean_deadline,
    }
    attachment = await _store_notice_pdf(pdf) if pdf else None
    if attachment:
        updates.update(attachment)
    try:
        updated = resubmit_notice(notice_id, user["id"], updates)
    except sqlite3.Error as error:
        if attachment:
            _delete_notice_pdf(attachment)
        raise HTTPException(status_code=500, detail="Unable to resubmit the notice") from error
    if not updated:
        if attachment:
            _delete_notice_pdf(attachment)
        raise HTTPException(status_code=409, detail="Notice status changed; refresh and try again")
    if attachment:
        _delete_notice_pdf(notice)
    log_activity(user["id"], "updated", "notice", notice_id, clean_title)
    return _public_notice(get_notice_by_id(notice_id))


@app.delete("/notices/{notice_id}/faculty")
async def delete_faculty_notice(
    notice_id: int,
    user=Depends(require_role(["faculty"])),
):
    notice = get_notice_by_id(notice_id)
    if not notice or notice["uploaded_by"] != user["id"]:
        raise HTTPException(status_code=404, detail="Notice not found")
    log_activity(user["id"], "deleted", "notice", notice_id, notice["title"])
    delete_notice(notice_id)
    _delete_notice_pdf(notice)
    return {"deleted": notice_id}


@app.post("/rag")
async def rag_query(
    payload: RagRequest,
    user=Depends(require_role(["student"])),
):
    notice = get_notice_by_id(payload.notice_id)
    if not notice or notice["status"] != "approved":
        raise HTTPException(status_code=404, detail="Approved notice not found")

    result = answer_question(
        payload.question,
        top_k=payload.top_k if payload.top_k is not None else 5,
        history=[turn.model_dump() for turn in payload.history],
        notice_id=payload.notice_id,
    )
    return {"question": payload.question, **result}


@app.get("/health")
async def health():
    return {"status": "ok"}
