"""argon2 runs off the event loop, at most `password_hash_concurrency` at a time."""

import asyncio
import threading
import time
from weakref import WeakKeyDictionary

import pytest

from app.core import security
from app.core.config import Settings
from app.core.security import (
    hash_password,
    hash_password_async,
    verify_against_dummy,
    verify_password_async,
)


async def _max_loop_lag(work: "asyncio.Future[object]") -> float:
    lag = 0.0
    while not work.done():
        start = time.perf_counter()
        await asyncio.sleep(0.005)
        lag = max(lag, time.perf_counter() - start - 0.005)
    return lag


async def test_verification_does_not_block_the_event_loop() -> None:
    stored = hash_password("correct horse battery")
    work = asyncio.gather(*(verify_password_async(stored, "wrong") for _ in range(4)))
    lag = await _max_loop_lag(work)
    assert await work == [False] * 4
    # One verification in the loop blocks it for ~65 ms; off the loop it stays responsive.
    assert lag < 0.03, lag


async def test_hashing_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "get_settings", lambda: Settings(password_hash_concurrency=2))
    monkeypatch.setattr(security, "_slots", WeakKeyDictionary())
    running, peak = 0, 0
    lock = threading.Lock()

    def slow_hash(password: str) -> str:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.05)
        with lock:
            running -= 1
        return "hash"

    monkeypatch.setattr(security, "hash_password", slow_hash)
    assert await asyncio.gather(*(hash_password_async("x") for _ in range(6))) == ["hash"] * 6
    assert peak == 2


async def test_async_helpers_agree_with_the_sync_ones() -> None:
    stored = await hash_password_async("a-long-password")
    assert await verify_password_async(stored, "a-long-password")
    assert not await verify_password_async(stored, "other")
    assert not await verify_against_dummy("a-long-password")
