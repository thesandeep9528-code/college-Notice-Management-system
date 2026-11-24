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
- Development uses a random process-only signing key if `AUTH_SECRET_KEY` is unset; restarting the API invalidates active sessions. Production must set `APP_ENV=production` and configure `AUTH_SECRET_KEY`.
- Passwords use PBKDF2-SHA256. Existing SHA-256 password hashes remain usable and upgrade after a successful login.
- Faculty notice creation derives the uploader from the authenticated account and always creates a pending notice.
- Students can only list/read approved notices; faculty can only list/read their own notices; administrator routes require the admin role.
- CORS defaults to local React development origins. Configure `CORS_ORIGINS` for other deployments.

## Admin role delivered

- Overview reports registered student/faculty counts, total/pending/approved/rejected notices, and recent audited actions.
- Account directory supports searching by name/email/department, role/status filtering, details, editing, account activation, and account creation.
- Notice archive supports search/status/category/department filters, metadata details/editing, and confirmed deletion.
- Approval queue supports approval confirmation and rejection with a required reason.
- Database upgrades add profile, notice metadata, and audit-log columns/tables without dropping existing users or notices.

## Remaining role and product work

- Faculty still needs a persistent “My Notices” workspace, PDF upload/storage/preview, rejection feedback, and permitted resubmit/edit/delete flows.
- Student search UI exists, but sorting, personalized targeting, notice detail/download, and deadlines need completion.
- `/rag` currently returns a placeholder echo; real retrieval, grounded answers, citations, and source-page links remain unimplemented.
- PDF files are not currently uploaded or served by the active API.
- The legacy PostgreSQL implementation has not been consolidated or migrated; preserve it until its data and purpose are explicitly reconciled.

## Validation

- Backend regression and API authorization tests: `python -m pytest -q`.
- Frontend production build: `cd frontend; npm run build`.
- API tests use isolated temporary SQLite files and cover signed-token tampering, active-account invalidation, faculty ownership, student visibility, admin summaries/filters, required rejection feedback, and additive schema migration.
