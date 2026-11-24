import hashlib

def hash_password(password: str) -> str:
    """Return a simple SHA256 hash of the password.
    Note: This is NOT secure for production; replace with a proper password hasher.
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Check a password against the stored SHA256 hash."""
    return hash_password(password) == hashed
