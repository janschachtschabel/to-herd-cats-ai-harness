"""Password hashing and session token primitives."""

import hashlib
import secrets
from functools import cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


@cache
def dummy_password_hash() -> str:
    """A hash of nothing in particular, verified when there is no account to check, so a
    login takes as long whether or not the address belongs to someone."""
    return _hasher.hash(secrets.token_urlsafe(16))


def new_session_token() -> str:
    """256-bit random token; only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
