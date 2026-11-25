# AI‑Powered College Notice Intelligence System ✨

A lightweight **React** web app for managing college notices and browsing approved announcements. Faculty can attach PDFs to notices, and students can search, sort, and explore approved updates with a locally grounded notice assistant.

---

## Table of Contents
| # | Section |
|---|---------|
| 1️⃣ | [Project Overview](#project-overview) |
| 2️⃣ | [Key Features](#key-features) |
| 3️⃣ | [Application Workflow](#application-workflow) |
| 4️⃣ | [System Architecture](#system-architecture) |
| 5️⃣ | [RAG Pipeline](#rag-pipeline) |
| 6️⃣ | [Technology Stack](#technology-stack) |
| 7️⃣ | [Folder Structure](#folder-structure) |
| 8️⃣ | [Installation & Setup](#installation-setup) |
| 9️⃣ | [Environment Variables](#environment-variables) |
| 🔟 | [Running the Project](#running-the-project) |
| 📸 | [Screenshots & Diagrams](#screenshots-diagrams) |
| 🚀 | [Future Improvements](#future-improvements) |
| 👤 | [Author](#author) |

---

## Project Overview
The system is built for a **single college** and provides three user roles:

| Role | Capabilities |
|------|--------------|
| **Student** | View only **approved** notices, search, filter, sort, track upcoming deadlines, preview/download PDFs, and ask questions against approved notice content. |
| **Faculty** | Submit notices with optional PDFs, track status, edit/resubmit rejected notices, and delete their own pending or rejected submissions. |
| **Admin** | Manage users, activate/deactivate accounts, approve/reject notices, and view activity logs. |

All role‑based restrictions are enforced **server‑side** (see `backend/main.py`).

---

## Key Features
| ✅ | Feature |
|---|---------|
| 📄 | Faculty can submit notices with metadata, deadlines, and optional PDFs (10 MiB limit), then track and manage permitted submissions. |
| ✅ | Admin can **approve**, **reject** or **delete** notices. |
| 📊 | Admin dashboard shows student/faculty totals, notice status counts, and recent audited actions. |
| 🔍 | Students can search by title/description, filter by category/department/semester, sort by date, prioritize profile-relevant notices, and see upcoming deadlines. |
| 🤖 | Student assistant searches approved notice metadata, descriptions, and extractable PDF text locally and returns source excerpts with page references when available. |
| 📑 | Students can view notice details and securely preview or download attached PDFs. |
| 🗂️ | PDF extraction (`services/pdf_service.py`) with optional OCR fallback. |
| 🧩 | Automatic notice intelligence (`services/notice_intelligence.py`) – categorisation, summary, deadline extraction, duplicate detection (file‑hash). |
| 📦 | Vector store powered by **Chromadb** (`services/notice_embedding.py`). |
| 🛡️ | API uses signed, expiring bearer tokens, active-account checks, role checks, and PBKDF2 password hashes. |
| 📁 | Admin account and notice changes are recorded in the SQLite activity log. |

---

## Application Workflow
```text
Student  ──► Search/Filter/Sort ► View Approved Notices
               │
               ├─► View details ► Preview/Download PDF
               └─► Ask question ► Local retrieval ► Grounded excerpts and sources
```
```text
Faculty  ──► Create Notice ► Save (status = pending)
               │
               └─► Optional PDF attachment is stored privately and served through an authorized API
```
```text
Admin    ──► Review Pending Notices ► Approve / Reject
               │
               └─► Approved → visible in the approved-notice list
               │
               └─► Rejected → excluded from student search
```
               The live API and UI are under `backend/` and `frontend/`. The top-level `database/` and `services/` folders contain older/prototype implementations and are not the database or RAG service currently used by the React app.
> **Diagram:** *Notice Upload & Approval Workflow*  
> ![Notice Upload & Approval Workflow](docs/images/notice_upload_approval.png)

---

## System Architecture
```
┌─────────────────────┐          ┌───────────────────────┐
│   React UI          │  HTTP    │  FastAPI Backend       │
│ (frontend/)         ◀─────────▶│  (services, database) │
└─────────────────────┘          └───────────────────────┘
          ▲                                 │
          │                                 ▼
   ┌───────────────┐                ┌───────────────┐
   │   SQLite DB   │  ←─SQL queries ┤   Chromadb    │
   │   (notice_intel)│            │ (vector store)│
   └───────────────┘                └───────────────┘
          ▲                                 │
          │                                 ▼
   ┌─────────────────────┐          ┌─────────────────────┐
   │   OpenAI API        │          │   LangGraph            │
   │   (Embeddings/LLM)  │          │   (RAG workflow)       │
   └─────────────────────┘          └─────────────────────┘
```
> **Diagram:** *Overall System Architecture*  
> ![Overall System Architecture](docs/images/system_architecture.png)

---

## AI Notice Assistant
The student-only `/rag` endpoint requires a selected approved notice ID and runs through a LangGraph workflow while keeping SQLite authoritative for notice metadata and approval status. Students select a notice from the existing filtered notice board; retrieval, PDF indexing, and answer context are restricted to that one notice. When configured, its metadata and extractable PDF page text are synced into the existing Chroma collection, used for OpenAI embedding retrieval, and passed to OpenAI for a source-cited answer. Results are checked against cited source text, with at most one retrieval retry. If OpenAI or Chroma credentials/services are unavailable, the assistant uses local retrieval within the same selected notice and returns excerpts instead of an ungrounded generated answer. PDF text is extracted page-by-page with PyPDF2; scanned image-only PDFs are not OCR-processed by the active assistant.

With `OPENAI_API_KEY` configured, only the selected approved notice text is sent to OpenAI for embeddings, and retrieved excerpts plus the student question are sent for answer generation. Use this only where that data sharing is permitted. The top-level `services/rag.py` remains a separate legacy Gemini implementation and is not called by FastAPI.

> **Diagram:** *PDF Processing & RAG Pipeline*  
> ![PDF Processing & RAG Pipeline](docs/images/pdf_rag_pipeline.png)

---

## Technology Stack
| Layer | Technology | Notes |
|-------|------------|-------|
| **UI** | **React** (JavaScript) | Front‑end built with Create‑React‑App (`react-scripts`). |
| **Backend** | **FastAPI** (Python 3.12) | Core API lives in `backend/main.py`. |
| **Database** | **SQLite** (via `sqlite3`) | Stores users, notices, and auto‑generated metadata. |
| **Vector Store** | **ChromaDB** | Stores approved notice metadata and PDF text chunks for semantic retrieval. |
| **LLM orchestration** | **LangGraph** | Typed state graph with bounded retries and source-grounded fallback. |
| **Embeddings / answer generation** | **OpenAI API** | Optional; configured with `OPENAI_API_KEY`. |
| **PDF extraction** | **PyPDF2** (fallback OCR uses `pdf2image` + `pytesseract` if installed). |
| **Intelligence** | SQLite (`services/sqlite_helper.py`) | Stores auto‑generated metadata (category, summary, deadline, hash). |
| **Authentication** | HMAC-signed expiring bearer tokens; PBKDF2 password hashes with legacy SHA-256 upgrade on login. |
| **Logging** | Admin audit events stored in the application SQLite database. |
| **Testing** | `pytest` | Test suite under `tests/`. |

> **Diagram:** *Technology Stack Overview*  
> ![Technology Stack Overview](docs/images/technology_stack.png)

---

## Folder Structure
```
ai-college-notice/
│
├─ .venv/                     # Python virtual environment (auto‑created)
├─ frontend/                  # React front‑end
│   ├─ public/
│   └─ src/
├─ backend/                   # FastAPI entry point (`main.py`)
├─ database/                  # SQLite helpers and auth
├─ services/                  # PDF, RAG, embedding, intelligence
├─ evaluation/
│   └─ dataset.json           # Manual evaluation dataset (Phase 11)
├─ tests/                     # pytest suite
├─ docs/
│   └─ images/                # Diagram PNGs referenced in README
├─ logs/                      # Admin activity log
├─ .gitignore
├─ requirements.txt
└─ README.md                  # ← **this file**
```

---

## Installation & Setup
> **⚠️ The project is developed for Windows.** Adjust paths if you use another OS.

1. **Clone the repo** (or open the existing workspace).  
   ```bash
   git clone <your‑repo‑url>
   cd ai-college-notice
   ```
2. **Create a virtual environment** (the repo already ships a `.venv` folder, but you can rebuild it):  
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. **Install Python dependencies**  
   ```bash
   .venv\Scripts\pip install -r requirements.txt
   ```
   *If `chromadb` fails to install on Windows, the repository already contains an in‑memory fallback stub that lets the app and tests run.*
4. **Create a `.env` file** in the project root (see next section) and add required secrets.
5. **Initialize the database**  
   ```bash
   .venv\Scripts\python -c "from backend.database.connection import init_db; init_db()"
   ```
   The backend initializes its schema additively at startup and creates a default admin when one does not exist:
   ```
   email: admin@example.com
   ```
   The seeded admin password is for local development only. Set a unique password before allowing anyone else to access the app.

---

## Environment Variables
Create a **`.env`** file in the repository root (do **not** commit it).  

| Variable | Description | Example |
|----------|-------------|---------|
| `AUTH_SECRET_KEY` | Stable secret used to sign API tokens; required in production. Without it, development uses a process-only random secret and restarts sign users out. | Generate a private random value |
| `APP_ENV` | Set to `production` to require `AUTH_SECRET_KEY`. | `production` |
| `CORS_ORIGINS` | Comma-separated allowed browser origins. Defaults to local React development origins. | `https://notices.example.edu` |
| `REACT_APP_API_URL` | Optional frontend API base URL; defaults to `http://127.0.0.1:8000`. | `https://api.example.edu` |
| `NOTICE_UPLOAD_DIR` | Optional directory for private notice PDF storage. Defaults to `backend/uploads/notices`; use persistent storage in deployments. | `D:\notice-data\pdfs` |
| `OPENAI_API_KEY` | Enables OpenAI embeddings, Chroma retrieval, and answer generation. Approved notice text and retrieved excerpts are sent to OpenAI; without this key, the assistant uses local retrieval and excerpt-only responses. | Set privately in the backend environment |
| `OPENAI_CHAT_MODEL` | OpenAI chat model used for answer generation. | `gpt-4o-mini` |
| `CHROMA_DB_PATH` | Optional path for the existing persistent `notice_chunks` Chroma collection. | `chromadb` |

The active SQLite file is `backend/ai_notice.db`. Schema initialization adds missing columns/tables without dropping existing users or notices.

For local development, the login page can show demo-account credentials from `frontend/.env.development.local`. Set `REACT_APP_SHOW_DEMO_CREDENTIALS=true` and provide `REACT_APP_DEMO_ADMIN_EMAIL`, `REACT_APP_DEMO_ADMIN_PASSWORD`, `REACT_APP_DEMO_FACULTY_EMAIL`, `REACT_APP_DEMO_FACULTY_PASSWORD`, `REACT_APP_DEMO_STUDENT_EMAIL`, and `REACT_APP_DEMO_STUDENT_PASSWORD`. This file is Git-ignored and only loaded by the React development server; do not copy credentials into this README or commit them. Anyone using the development server can see the credentials. Use only disposable local demo accounts and restart `npm start` after changing the file.

---

## Running the Project
```bash
# Activate the venv first if not already active
.venv\Scripts\activate

# Start the FastAPI backend
uvicorn backend.main:app --reload
```
Open `http://127.0.0.1:8000/docs` to explore the OpenAPI UI, or run the React front‑end:
```bash
cd frontend
npm install   # requires internet
npm start
```
The React app will be served at `http://localhost:3000` and communicate with the FastAPI backend.

---

## Screenshots & Diagrams
| Description | Image |
|-------------|-------|
| **Notice Upload & Approval Workflow** | ![Notice Upload & Approval Workflow](docs/images/notice_upload_approval.png) |
| **PDF Processing & RAG Pipeline** | ![PDF Processing & RAG Pipeline](docs/images/pdf_rag_pipeline.png) |
| **Overall System Architecture** | ![Overall System Architecture](docs/images/system_architecture.png) |
| **Technology Stack Overview** | ![Technology Stack Overview](docs/images/technology_stack.png) |

*The images are simple placeholders. Replace them with detailed graphics when you have them.*

---

## Future Improvements
| # | Planned Feature | Status |
|---|----------------|--------|
| 🚧 | PDF upload, private storage, and role-checked preview/download. | Implemented for Faculty and students. |
| 🚧 | Automatic notice categorisation, summarisation & deadline extraction – integrate into upload flow. | **Phase 10** – backend ready, UI pending. |
| 🚧 | Duplicate‑notice detection using file hash. | Implemented in `notice_intelligence.py`. |
| 🚧 | Semantic/vector retrieval using the legacy ChromaDB prototype. | Not connected to the active app; current retrieval is local keyword matching. |
| 🚧 | Deployment scripts (Docker, Kubernetes) | Not required for the current portfolio demo. |
| 🚧 | Expand tests for authentication, permissions, notice workflows, sorting, and assistant sources. | Core API and source-visibility cases are covered; expand as features grow. |

---



👨‍💻**About Me**

Sandeep Kumar
B.Tech Student | Computer Science / IT

- 💻 Interested in Generative AI and Backend Development.
- 🤖 Exploring LLMs, RAG Systems, and AI-powered applications.
- 🚀 Building practical projects to solve real-world problems.

Connect with me:

- LinkedIn: https://www.linkedin.com/in/sandeep-kumar-488581423

Feel free to open issues or submit pull requests for enhancements!
