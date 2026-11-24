# AI‑Powered College Notice Intelligence System ✨

A lightweight Streamlit web‑app that lets a college community **upload, manage, search and query PDF notices**.  Students can **search by keywords, filter by category/department/semester, and ask natural‑language questions** backed by a Retrieval‑Augmented Generation (RAG) pipeline powered by Google Gemini.

---

## Table of Contents
| # | Section |
|---|---------|
| 1️⃣ | [Project Overview](#project-overview) |
| 2️⃣ | [Key Features](#key-features) |
| 3️⃣ | [Application Workflow](#application‑workflow) |
| 4️⃣ | [System Architecture](#system‑architecture) |
| 5️⃣ | [RAG Pipeline](#rag‑pipeline) |
| 6️⃣ | [Technology Stack](#technology‑stack) |
| 7️⃣ | [Folder Structure](#folder‑structure) |
| 8️⃣ | [Installation & Setup](#installation‑setup) |
| 9️⃣ | [Environment Variables](#environment-variables) |
| 🔟 | [Running the App](#running-the-app) |
| 📸 | [Screenshots & Diagrams](#screenshots‑diagrams) |
| 🚀 | [Future Improvements](#future‑improvements) |
| 👤 | [Author](#author) |

---

## Project Overview
The system is built for a **single college** and provides three user roles:

| Role | Capabilities |
|------|--------------|
| **Student** | View only **approved** notices, search, filter, and ask RAG‑based questions. |
| **Faculty** | Create new notices (PDF upload placeholder for now) and view their own submissions. |
| **Admin** | Manage users, activate/deactivate accounts, approve/reject notices, and view activity logs. |

All role‑based restrictions are enforced **server‑side** (see `app/app.py`).  

---

## Key Features
| ✅ | Feature |
|---|---------|
| 📄 | Faculty can add a new notice (title, description, category, department, semester). |
| ✅ | Admin can **approve**, **reject** or **delete** notices. |
| 📊 | Admin dashboard shows total numbers of students & faculty and activity logs. |
| 🔍 | Students can **search** by title/description, filter by category, department & semester. |
| 🤖 | RAG chatbot (`services/rag.py`) answers questions using **Google Gemini** and returns **source citations**. |
| 🗂️ | PDF extraction (`services/pdf_service.py`) with optional OCR fallback. |
| 🧩 | Automatic notice intelligence (`services/notice_intelligence.py`) – categorisation, summary, deadline extraction, duplicate detection (file‑hash). |
| 📦 | Vector store powered by **Chromadb** (`services/notice_embedding.py`). |
| 🛡️ | Passwords stored as **hashed** values (`database/auth.py`). |
| 📁 | Activity logging for admin actions (`logs/admin.log`). |

---

## Application Workflow
```text
Student  ──► Search/Filter ► View Approved Notices
               │
               └─► Ask question ► RAG pipeline ► Gemini answer + citations
```
```text
Faculty  ──► Create Notice ► Save (status = pending)
               │
               └─► (Upload placeholder – real PDF upload to be added)
```
```text
Admin    ──► Review Pending Notices ► Approve / Reject
               │
               └─► Approved → process_approved_notices() → embed in Chromadb
               │
               └─► Rejected → excluded from student search
```

> **Diagram:** *Notice Upload & Approval Workflow*  
> ![Notice Upload & Approval Workflow](docs/images/notice_upload_approval.png)

---

## System Architecture
```
┌─────────────────────┐          ┌───────────────────────┐
│   Streamlit UI      │  HTTP    │  Fast Python Backend   │
│ (app/app.py)        ◀─────────▶│  (services, database) │
└─────────────────────┘          └───────────────────────┘
          ▲                                 │
          │                                 ▼
   ┌───────────────┐                ┌───────────────┐
   │   PostgreSQL  │  ←─SQL queries ┤   Chromadb    │
   │   (psycopg2)  │                │ (vector store)│
   └───────────────┘                └───────────────┘
          ▲                                 │
          │                                 ▼
   ┌─────────────────────┐          ┌─────────────────────┐
   │   SQLite (Intel)    │          │  Google Gemini API  │
   │   (notice_intel)    │          │  (gemini‑1.5‑flash)│
   └─────────────────────┘          └─────────────────────┘
```

> **Diagram:** *Overall System Architecture*  
> ![Overall System Architecture](docs/images/system_architecture.png)

---

## RAG Pipeline
1. **Retrieve relevant chunks** – `services/notice_embedding.search_similar()` queries Chromadb.  
2. **Build prompt** – context fragments + user question.  
3. **Generate answer** – `google.generativeai` Gemini model.  
4. **Add citations** – unique `(filename, page_number)` pairs are rendered under **Sources**.  

> **Diagram:** *PDF Processing & RAG Pipeline*  
> ![PDF Processing & RAG Pipeline](docs/images/pdf_rag_pipeline.png)

---

## Technology Stack
| Layer | Technology | Notes |
|-------|------------|-------|
| **UI** | **Streamlit** (Python) | Simple web UI, runs with `streamlit run app/app.py`. |
| **Backend** | Python 3.10+ | Core logic lives in `services/` and `database/`. |
| **Database** | **PostgreSQL** (via `psycopg2`) | Stores users & notices. |
| **Vector Store** | **Chromadb** (local SQLite) | Stores text embeddings for RAG. |
| **LLM** | **Google Gemini 1.5 Flash** (`google.generativeai`) | Requires `GEMINI_API_KEY`. |
| **PDF extraction** | **PyPDF2** (fallback OCR uses `pdf2image` + `pytesseract` if installed). |
| **Intelligence** | SQLite (`services/sqlite_helper.py`) | Stores auto‑generated metadata (category, summary, deadline, hash). |
| **Authentication** | Password hashing (`bcrypt` via `database/auth.py`). |
| **Logging** | Plain‑text file (`logs/admin.log`). |
| **Testing** | `pytest` | Test suite under `tests/`. |

> **Diagram:** *Technology Stack Overview*  
> ![Technology Stack Overview](docs/images/technology_stack.png)

---

## Folder Structure
```
ai-college-notice/
│
├─ .venv/                     # Python virtual environment (auto‑created)
├─ app/
│   └─ app.py                 # Streamlit entry point
├─ database/
│   ├─ config.py              # DB connection settings (env‑vars)
│   ├─ connection.py          # psycopg2 connection helper
│   ├─ queries.py             # CRUD helpers
│   ├─ auth.py                # Password hashing & verification
│   └─ seed_admin.py          # Creates a default admin user
├─ services/
│   ├─ pdf_service.py         # PDF → text + optional OCR
│   ├─ rag.py                 # RAG answer generation
│   ├─ notice_embedding.py    # Chromadb wrapper (fallback stub already in repo)
│   ├─ notice_intelligence.py# Auto‑metadata extraction & SQLite storage
│   └─ sqlite_helper.py       # Helper for the intel SQLite DB
├─ evaluation/
│   └─ dataset.json           # Manual evaluation dataset (Phase 11)
├─ tests/
│   ├─ conftest.py
│   ├─ test_citation_metadata.py
│   ├─ test_pdf_service.py
│   └─ test_queries.py
├─ docs/
│   └─ images/                # Diagram PNGs referenced in README
├─ logs/
│   └─ admin.log              # Admin activity log (runtime)
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
   .venv\Scripts\python -c "from database.connection import init_db; init_db()"
   ```
   The `seed_admin.py` script runs automatically at app start and creates a default admin:
   ```
   email: admin@example.com
   password: admin123
   ```

---

## Environment Variables
Create a **`.env`** file in the repository root (do **not** commit it).  

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port (default 5432) | `5432` |
| `DB_NAME` | Database name | `college_notice` |
| `DB_USER` | DB user | `postgres` |
| `DB_PASSWORD` | DB password | `postgres` |
| `GEMINI_API_KEY` | Google Gemini API key (required for RAG) | `AIzaSy...` |
| `PYTHONPATH` *(optional)* | Include project root for imports | `.` |

The `database/config.py` file reads these variables with sensible defaults, so the app will still start with a local PostgreSQL instance if you don't provide them.

---

## Running the Project
```bash
# Activate the venv first if not already active
.venv\Scripts\activate

# Run the Streamlit UI
.venv\Scripts\streamlit run app/app.py
```
Open the displayed URL (usually `http://localhost:8501`) in a browser.  
Log in with the seeded admin credentials, create student/faculty accounts, upload notices, approve them, and start asking questions!

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
| 🚧 | Automatic notice categorisation, summarisation & deadline extraction (already in `notice_intelligence.py`) – integrate into upload flow. | **Phase 10** – backend ready, UI pending. |
| 🚧 | Duplicate‑notice detection using file hash. | Implemented in `notice_intelligence.py`. |
| 🚧 | Semantic search UI (vector similarity ranking) | RAG already uses Chromadb; a dedicated search page can be added. |
| 🚧 | Deployment scripts (Docker, Kubernetes) | Not required for the current portfolio demo. |
| 🚧 | Unit‑test coverage for authentication, permission checks, and RAG citation formatting. | Added in Phase 11. |

---

## Author
**Sandeep Kumar** – AI College Notice Intern  
LinkedIn: [https://www.linkedin.com/in/sandeep-kumar-488581423](https://www.linkedin.com/in/sandeep-kumar-488581423)  
GitHub: https://github.com/yourusername  

Feel free to open issues or submit pull requests for enhancements!
