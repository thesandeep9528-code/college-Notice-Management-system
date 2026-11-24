# Project Context

## Current application entry points

- React UI: `frontend/src/App.js` and `frontend/src/App.css`.
- FastAPI API: `backend/main.py`.
- Active database and schema initialization: `backend/database/connection.py`.
- Active SQLite queries and audit events: `backend/database/queries.py`.
- Active assistant implementation: `backend/services/rag.py` (currently a placeholder).
- Local database file: `backend/ai_notice.db`; schema startup performs additive changes only.

The top-level `database/` and `services/` directories contain older or prototype implementations. The React app currently calls the `backend/` API and does not use the top-level PostgreSQL database.

## Shared security foundation delivered

- Bearer tokens are HMAC-signed and expire after eight hours. Roles are read from the database, not trusted from token claims.
- Protected requests resolve the account and reject inactive or deleted accounts.
- Development uses a random process-only signing key if `AUTH_SECRET_KEY` is unset; restarting the API invalidates active sessions. Production must set `APP_ENV=production` and configure an `AUTH_SECRET_KEY` of at least 32 bytes.
- Passwords use PBKDF2-SHA256. Existing SHA-256 password hashes remain usable and upgrade after a successful login.
- Faculty notice creation derives the uploader from the authenticated account and always creates a pending notice.
- Students can only list/read approved notices; faculty can only list/read their own notices and attachments; administrator routes require the admin role.
- CORS defaults to local React development origins. Configure `CORS_ORIGINS` for other deployments.

## Admin role delivered

- Overview reports registered student/faculty counts, total/pending/approved/rejected notices, and recent audited actions.
- Account directory supports searching by name/email/department, role/status filtering, details, editing, account activation, and account creation.
- Notice archive supports search/status/category/department filters, metadata details/editing, and confirmed deletion.
- Approval queue supports approval confirmation and rejection with a required reason.
- Database upgrades add profile, notice metadata, and audit-log columns/tables without dropping existing users or notices.

## Faculty role delivered

- Overview reports the faculty member's total, approved, pending, and rejected notices plus the five most recent submissions.
- “My notices” is owner-scoped and supports search and status/category filters, approval status, and rejection feedback.
- Notices can include an optional PDF up to 10 MiB. The server validates the extension, media type, and PDF signature, stores files under a generated private name, and serves them only through authenticated role-scoped routes.
- The upload form includes upload progress and an in-browser PDF preview. Faculty can download/preview their attachments.
- Faculty can edit/resubmit rejected notices; resubmission clears the rejection reason and returns the notice to pending review. They may delete their own pending or rejected notices; approved notices require Admin removal.
- `NOTICE_UPLOAD_DIR` configures attachment storage. The default `backend/uploads/notices/` is gitignored; deployments should use persistent storage.

## Remaining role and product work

- Student search UI exists, but sorting, personalized targeting, notice detail/download UI, and upcoming-deadline views need completion. The secure PDF API is ready for that UI.
- `/rag` currently returns a placeholder echo; real retrieval, grounded answers, citations, and source-page links remain unimplemented.
- The legacy PostgreSQL implementation has not been consolidated or migrated; preserve it until its data and purpose are explicitly reconciled.

## Validation

- Backend regression and API authorization tests: `python -m pytest -q`.
- Frontend production build: `cd frontend; npm run build`.
- API tests use isolated temporary SQLite files and cover token tampering, active-account invalidation, faculty ownership, PDF size/type checks and visibility, rejected-notice resubmission, student access boundaries, Admin workflows, and additive schema migration.
