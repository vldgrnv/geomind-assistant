import hashlib
import hmac
import os

PBKDF2_ITERATIONS = 200_000
PBKDF2_SCHEME = "pbkdf2_sha256"
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{PBKDF2_SCHEME}${PBKDF2_ITERATIONS}${salt}${digest}"


def _verify_pbkdf2(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt, expected = encoded.split("$", 3)
    except ValueError:
        return False
    if scheme != PBKDF2_SCHEME:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        int(iterations),
    ).hex()
    return hmac.compare_digest(actual, expected)


def verify_password(password: str, stored_hash: str) -> tuple[bool, bool]:
    if not stored_hash:
        return False, False
    if stored_hash.startswith(PBKDF2_SCHEME + "$"):
        return _verify_pbkdf2(password, stored_hash), False

    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    is_valid = hmac.compare_digest(legacy, stored_hash)
    return is_valid, is_valid
