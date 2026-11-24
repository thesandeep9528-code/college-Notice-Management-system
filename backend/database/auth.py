import hashlib
import hmac
import secrets


_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS
    )
    return f"{_PASSWORD_SCHEME}${_PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not isinstance(stored_hash, str):
        return False

    if stored_hash.startswith(f"{_PASSWORD_SCHEME}$"):
        try:
            scheme, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
            if scheme != _PASSWORD_SCHEME:
                return False
            iteration_count = int(iterations)
            if not 100_000 <= iteration_count <= 1_000_000:
                return False
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
        except (ValueError, TypeError):
            return False

        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iteration_count
        )
        return hmac.compare_digest(actual, expected)

    # Existing accounts use an unsalted SHA-256 hash; keep login compatible
    # and upgrade the hash after a successful login.
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash)


def needs_rehash(stored_hash: str) -> bool:
    return not stored_hash.startswith(f"{_PASSWORD_SCHEME}${_PASSWORD_ITERATIONS}$")
