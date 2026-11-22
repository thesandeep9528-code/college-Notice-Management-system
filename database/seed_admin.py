import os
import secrets
from .connection import get_connection
from .auth import hash_password

def seed_admin():
    """Create an admin user if none exists.
    Reads ADMIN_EMAIL and ADMIN_PASSWORD from environment variables.
    If ADMIN_PASSWORD is not provided, a random 12‑char password is generated
    and printed to the console (so you can note it down).
    """
    email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
    password = os.getenv('ADMIN_PASSWORD')
    if not password:
        password = secrets.token_urlsafe(12)
        print(f"[seed_admin] Generated admin password: {password}")
    pwd_hash = hash_password(password)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Check if an admin already exists
            cur.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1;")
            if cur.fetchone():
                print('[seed_admin] Admin user already exists – skipping creation.')
                return
            # Insert admin
            cur.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES (%s, %s, 'admin')
                RETURNING id;
                """,
                (email, pwd_hash),
            )
            admin_id = cur.fetchone()[0]
            conn.commit()
            print(f"[seed_admin] Created admin user id={admin_id}, email={email}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_admin()
