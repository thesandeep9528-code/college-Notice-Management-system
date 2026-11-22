# Migration script to ensure DB tables exist
# Run this once (or on every app start) to create tables if they are missing.

from .connection import init_db

if __name__ == "__main__":
    init_db()
    print("✅ Database tables are ready.")
