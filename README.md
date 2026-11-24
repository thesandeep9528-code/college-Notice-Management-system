# AI‑Powered College Notice Intelligence System ✨

A lightweight **React** web app for managing college notices and browsing approved announcements. Students can search by keywords and filters. PDF upload and a live Retrieval-Augmented Generation (RAG) assistant remain future work.

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
| **Student** | View only **approved** notices, search, filter, and ask RAG‑based questions. |
| **Faculty** | Submit text notices for review; a dedicated submissions-management and PDF-upload workflow remains future work. |
| **Admin** | Manage users, activate/deactivate accounts, approve/reject notices, and view activity logs. |

All role‑based restrictions are enforced **server‑side** (see `backend/main.py`).

---

## Key Features
| ✅ | Feature |
|---|---------|
| 📄 | Faculty can add a new notice (title, description, category, department, semester). |
| ✅ | Admin can **approve**, **reject** or **delete** notices. |
| 📊 | Admin dashboard shows student/faculty totals, notice status counts, and recent audited actions. |
| 🔍 | Students can **search** by title/description, filter by category, department & semester. |
| 🤖 | Student assistant UI is present; its current backend response is a placeholder, not a live RAG answer. |
| 🗂️ | PDF extraction (`services/pdf_service.py`) with optional OCR fallback. |
| 🧩 | Automatic notice intelligence (`services/notice_intelligence.py`) – categorisation, summary, deadline extraction, duplicate detection (file‑hash). |
| 📦 | Vector store powered by **Chromadb** (`services/notice_embedding.py`). |
| 🛡️ | API uses signed, expiring bearer tokens, active-account checks, role checks, and PBKDF2 password hashes. |
| 📁 | Admin account and notice changes are recorded in the SQLite activity log. |

---

## Application Workflow
```text
Student  ──► Search/Filter ► View Approved Notices
               │
               └─► Ask question ► Placeholder response (RAG integration remains future work)
```
```text
Faculty  ──► Create Notice ► Save (status = pending)
               │
               └─► (Upload placeholder – real PDF upload to be added)
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
   │   OpenAI API        │          │   ChatGPT (gpt‑4‑turbo)│
   │   (ChatGPT)         │          │   (Answer generation)│
   └─────────────────────┘          └─────────────────────┘
```
> **Diagram:** *Overall System Architecture*  
> ![Overall System Architecture](docs/images/system_architecture.png)

---

## AI Notice Assistant
The current React app calls `backend/services/rag.py`, which returns a placeholder response. The separate top-level `services/notice_embedding.py` and PDF processing modules are prototypes; they are not yet connected to the active API flow. Live retrieval, grounded answers, citations, and PDF upload are planned work.

> **Diagram:** *PDF Processing & RAG Pipeline*  
> ![PDF Processing & RAG Pipeline](docs/images/pdf_rag_pipeline.png)

---

## Technology Stack
| Layer | Technology | Notes |
|-------|------------|-------|
| **UI** | **React** (JavaScript) | Front‑end built with Create‑React‑App (`react-scripts`). |
| **Backend** | **FastAPI** (Python 3.12) | Core API lives in `backend/main.py`. |
| **Database** | **SQLite** (via `sqlite3`) | Stores users, notices, and auto‑generated metadata. |
| **Vector Store** | **Chromadb** (local SQLite) | Stores text embeddings for RAG. |
| **LLM** | Not connected in the active backend | The `/rag` endpoint currently returns a placeholder response. |
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
   password: admin123
   ```

---

## Environment Variables
Create a **`.env`** file in the repository root (do **not** commit it).  

| Variable | Description | Example |
|----------|-------------|---------|
| `AUTH_SECRET_KEY` | Stable secret used to sign API tokens; required in production. Without it, development uses a process-only random secret and restarts sign users out. | Generate a private random value |
| `APP_ENV` | Set to `production` to require `AUTH_SECRET_KEY`. | `production` |
| `CORS_ORIGINS` | Comma-separated allowed browser origins. Defaults to local React development origins. | `https://notices.example.edu` |
| `REACT_APP_API_URL` | Optional frontend API base URL; defaults to `http://127.0.0.1:8000`. | `https://api.example.edu` |
| `OPENAI_API_KEY` | Reserved for the future RAG integration; the current active `/rag` implementation does not use it. | Set only when integrating RAG |

The active SQLite file is `backend/ai_notice.db`. Schema initialization adds missing columns/tables without dropping existing users or notices.

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
| 🚧 | Real PDF file upload & storage (instead of placeholder path) | **Phase 9** – partially implemented (UI ready). |
| 🚧 | Automatic notice categorisation, summarisation & deadline extraction – integrate into upload flow. | **Phase 10** – backend ready, UI pending. |
| 🚧 | Duplicate‑notice detection using file hash. | Implemented in `notice_intelligence.py`. |
| 🚧 | Semantic search UI (vector similarity ranking) | RAG already uses Chromadb; a dedicated search page can be added. |
| 🚧 | Deployment scripts (Docker, Kubernetes) | Not required for the current portfolio demo. |
| 🚧 | Unit‑test coverage for authentication, permission checks, and RAG citation formatting. | Added in Phase 11. |

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
