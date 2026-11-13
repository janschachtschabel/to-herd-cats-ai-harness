"""argon2 runs off the event loop, at most `password_hash_concurrency` at a time."""

import asyncio
import threading
import time
from weakref import WeakKeyDictionary

import pytest

from app.core import security
from app.core.config import Settings
from app.core.security import (
    HashingBusy,
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
    monkeypatch.setattr(security, "_gates", WeakKeyDictionary())
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


async def test_the_queue_for_hashing_slots_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """One slot, two may wait: of six at once three are hashed, three refused at once."""
    settings = Settings(password_hash_concurrency=1, password_hash_queue=2)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "_gates", WeakKeyDictionary())
    monkeypatch.setattr(security, "hash_password", lambda password: time.sleep(0.1) or "hash")

    async def attempt() -> tuple[str, float]:
        started = time.perf_counter()
        try:
            return await hash_password_async("x"), time.perf_counter() - started
        except HashingBusy:
            return "busy", time.perf_counter() - started

    results = await asyncio.gather(*(attempt() for _ in range(6)))
    assert sorted(r for r, _ in results) == ["busy"] * 3 + ["hash"] * 3
    assert all(took < 0.05 for r, took in results if r == "busy")
    # Once the queue has room again, requests are served.
    assert await hash_password_async("x") == "hash"
