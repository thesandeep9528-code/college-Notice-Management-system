import os
import hashlib
import binascii

# -------------------------------------------------------------------
# Password hashing utilities (using PBKDF2-HMAC-SHA256)
# -------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Return a salted hash of the password.
    The format is ``salt$hash`` where both parts are hex strings.
    Uses PBKDF2-HMAC with 100,000 iterations – secure for a demo app.
    """
    salt = os.urandom(16)  # 128‑bit random salt
    # Derive a 32‑byte (256‑bit) key
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    # Store as hex for easy DB storage
    return f"{binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against the stored ``salt$hash`` value.
    Returns ``True`` if the password matches, ``False`` otherwise.
    """
    try:
        salt_hex, hash_hex = stored.split('$')
        salt = binascii.unhexlify(salt_hex)
        expected_hash = binascii.unhexlify(hash_hex)
        test_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
        return hashlib.compare_digest(test_hash, expected_hash)
    except Exception:
        # Any parsing error – treat as non‑match
        return False
