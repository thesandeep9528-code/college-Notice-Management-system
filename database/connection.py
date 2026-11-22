import psycopg2
import psycopg2.extras
from .config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def get_connection():
    """Return a new psycopg2 connection using the config values.
    The connection uses a DictCursor so rows behave like dictionaries.
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    return conn

def init_db():
    """Create the required tables if they don't exist.
    This function is idempotent – running it multiple times is safe.
    """
    conn = get_connection()
    # Ensure the notices table has a deadline column (optional)
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE notices
            ADD COLUMN IF NOT EXISTS deadline TIMESTAMP WITH TIME ZONE;
        """)
    conn.commit()
    try:
        with conn.cursor() as cur:
            # Users table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(20) CHECK (role IN ('student', 'faculty', 'admin')) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # Notices table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS notices (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    category VARCHAR(100),
                    department VARCHAR(100),
                    semester VARCHAR(20),
                    uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    file_path VARCHAR(500),
                    status VARCHAR(20) CHECK (status IN ('pending', 'approved', 'rejected')) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        conn.commit()
    finally:
        conn.close()
