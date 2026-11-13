"""Password hashing and session token primitives.

argon2 is slow and memory-hard on purpose (~65 ms, 64 MiB each). Request code uses the
`*_async` helpers: they run it in a worker thread (argon2-cffi releases the GIL), at
most `HERD_PASSWORD_HASH_CONCURRENCY` at a time per process, so the event loop stays
responsive and memory stays bounded (concurrency × 64 MiB). At most
`HERD_PASSWORD_HASH_QUEUE` more wait for a slot; beyond that a request is answered at
once with 429 `server.busy` and `Retry-After` (`HashingBusy`).

Callers hold no database connection and no lock while they wait or hash (they commit
first and re-read afterwards), so a flood of logins cannot exhaust the pool.
"""

import asyncio
import hashlib
import secrets
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from functools import cache
from weakref import WeakKeyDictionary

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import RateLimited

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


class HashingBusy(RateLimited):
    """Every hashing slot is taken and the queue is full: try again in a moment."""

    code = "server.busy"
    retry_after = 1


class _Gate:
    """`slots` hashing at a time; at most `queue` more wait, the rest are refused."""

    def __init__(self, slots: int, queue: int) -> None:
        self._slots = asyncio.Semaphore(slots)
        self._queue = queue
        self._waiting = 0

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        if self._slots.locked() and self._waiting >= self._queue:
            raise HashingBusy()
        self._waiting += 1
        try:
            await self._slots.acquire()
        finally:
            self._waiting -= 1
        try:
            yield
        finally:
            self._slots.release()


_gates: "WeakKeyDictionary[asyncio.AbstractEventLoop, _Gate]" = WeakKeyDictionary()


def _slot() -> AbstractAsyncContextManager[None]:
    """A hashing slot of this process (one gate per event loop)."""
    loop = asyncio.get_running_loop()
    gate = _gates.get(loop)
    if gate is None:
        settings = get_settings()
        gate = _gates[loop] = _Gate(
            settings.password_hash_concurrency, settings.password_hash_queue
        )
    return gate.slot()


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
