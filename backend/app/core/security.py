"""Password hashing and session token primitives.

argon2 is slow and memory-hard on purpose (~65 ms, 64 MiB each). Request code uses the
`*_async` helpers: they run it in a worker thread (argon2-cffi releases the GIL), at
most `HERD_PASSWORD_HASH_CONCURRENCY` at a time per process, so the event loop, and
with it the probes and every other request, stays responsive, and memory stays
bounded (concurrency × 64 MiB).
"""

import asyncio
import hashlib
import secrets
from functools import cache
from weakref import WeakKeyDictionary

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

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


_slots: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = WeakKeyDictionary()


def _slot() -> asyncio.Semaphore:
    """The process's hashing slots (one semaphore per event loop)."""
    loop = asyncio.get_running_loop()
    slot = _slots.get(loop)
    if slot is None:
        slot = _slots[loop] = asyncio.Semaphore(get_settings().password_hash_concurrency)
    return slot


async def hash_password_async(password: str) -> str:
    async with _slot():
        return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password_hash: str, password: str) -> bool:
    async with _slot():
        return await asyncio.to_thread(verify_password, password_hash, password)


async def verify_against_dummy(password: str) -> bool:
    """The work of a verification without an account (always False)."""
    async with _slot():
        return await asyncio.to_thread(lambda: verify_password(dummy_password_hash(), password))


def new_session_token() -> str:
    """256-bit random token; only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
