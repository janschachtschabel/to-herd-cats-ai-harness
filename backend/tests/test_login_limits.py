"""Login rate limits under real concurrency (real commits, separate connections).

- Per client address and email only failures count, and the count is atomic.
- Per client address all attempts count, whatever the email (bounds password hashing).
- Someone at another address cannot lock a person out.
- Stale counters of any key are pruned.
"""

import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.config import Settings, get_settings
from app.core.failure_limit import PENDING, FailureLimiter
from app.core.models_base import utcnow
from app.core.ratelimit import PRUNE_BATCH, WINDOW, RateLimitHit, limit_key, prune_stale
from app.modules.audit.models import AuditLog
from tests.factories import CSRF, PASSWORD
from tests.real_db import MakeRealClient, RealDb
from tests.support.plans import force_nested_loops


def _limits(app: FastAPI, *, account: int = 5, per_ip: int = 1000) -> None:
    settings = Settings(login_rate_limit_per_minute=account, login_ip_rate_limit_per_minute=per_ip)
    app.dependency_overrides[get_settings] = lambda: settings


async def _attempt(client, email: str, password: str) -> int:
    body = {"email": email, "password": password}
    return (await client.post("/api/auth/login", json=body, headers=CSRF)).status_code


async def test_concurrent_wrong_passwords_get_exactly_the_limit(
    real_db: RealDb, real_app: FastAPI, make_real_client: MakeRealClient
) -> None:
    _limits(real_app, account=5)
    client = await make_real_client()
    codes = await asyncio.gather(
        *(_attempt(client, real_db.member_email, "wrong-password") for _ in range(20))
    )
    assert sorted(codes) == [401] * 5 + [429] * 15


async def test_another_address_cannot_lock_a_person_out(
    real_db: RealDb, real_app: FastAPI, make_real_client: MakeRealClient
) -> None:
    _limits(real_app, account=5)
    attacker = await make_real_client(client_ip="203.0.113.7")
    for _ in range(5):
        assert await _attempt(attacker, real_db.member_email, "wrong-password") == 401
    assert await _attempt(attacker, real_db.member_email, PASSWORD) == 429
    victim = await make_real_client(client_ip="198.51.100.2")
    assert await _attempt(victim, real_db.member_email, PASSWORD) == 200


async def test_successful_logins_do_not_count_against_the_account(
    real_db: RealDb, real_app: FastAPI, make_real_client: MakeRealClient
) -> None:
    _limits(real_app, account=2)
    client = await make_real_client()
    for _ in range(5):
        assert await _attempt(client, real_db.member_email, PASSWORD) == 200


async def test_concurrent_correct_logins_all_succeed(
    real_db: RealDb, real_app: FastAPI, make_real_client: MakeRealClient
) -> None:
    """Only completed failures count: correct logins in flight do not use up the limit."""
    _limits(real_app, account=5)
    client = await make_real_client()
    codes = await asyncio.gather(
        *(_attempt(client, real_db.member_email, PASSWORD) for _ in range(8))
    )
    assert codes == [200] * 8


async def test_one_address_is_limited_whatever_the_email(
    real_db: RealDb, real_app: FastAPI, make_real_client: MakeRealClient
) -> None:
    _limits(real_app, per_ip=10)
    client = await make_real_client(client_ip="203.0.113.9")
    codes = await asyncio.gather(
        *(_attempt(client, f"nobody{i}@example.com", "wrong-password") for i in range(15))
    )
    assert sorted(codes) == [401] * 10 + [429] * 5
    other = await make_real_client(client_ip="198.51.100.3")
    assert await _attempt(other, real_db.member_email, PASSWORD) == 200


async def test_stale_counters_of_any_key_are_pruned(
    real_db: RealDb, real_app: FastAPI, make_real_client: MakeRealClient
) -> None:
    _limits(real_app)
    old = utcnow() - WINDOW - timedelta(seconds=5)
    async with real_db.database.session_factory() as s:
        s.add_all(RateLimitHit(key=f"login-fail:x:{i}@example.com", hit_at=old) for i in range(50))
        await s.commit()
    client = await make_real_client()
    await _attempt(client, real_db.member_email, "wrong-password")
    async with real_db.database.session_factory() as s:
        stale = (
            select(func.count())
            .select_from(RateLimitHit)
            .where(RateLimitHit.key.like("login-fail:x:%"))
        )
        assert await s.scalar(stale) == 0
    assert PRUNE_BATCH >= 50


async def test_one_prune_removes_at_most_its_batch_whatever_the_plan(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A batch over `IN (subquery … LIMIT n FOR UPDATE SKIP LOCKED)` removes more
    than n under a nested-loop plan; it must hold whatever plan is picked."""
    monkeypatch.setattr(ratelimit, "PRUNE_BATCH", 2)
    long_ago = datetime(2001, 1, 1, tzinfo=UTC)
    session.add_all(RateLimitHit(key=f"prune-bound:{i}", hit_at=long_ago) for i in range(5))
    await session.flush()
    await force_nested_loops(session)
    await prune_stale(session, long_ago + timedelta(days=1))
    left = (
        select(func.count()).select_from(RateLimitHit).where(RateLimitHit.key.like("prune-bound:%"))
    )
    assert await session.scalar(left) == 3


async def test_an_ipv6_prefix_counts_as_one_address(
    real_db: RealDb, real_app: FastAPI, make_real_client: MakeRealClient
) -> None:
    """One IPv6 host controls a whole /64: rotating within it does not reset a limit."""
    _limits(real_app, per_ip=3)
    codes = []
    for host in range(1, 5):
        client = await make_real_client(client_ip=f"2001:db8:1:2::{host}")
        codes.append(await _attempt(client, f"nobody{host}@example.com", "wrong-password"))
    assert codes == [401, 401, 401, 429]
    neighbour = await make_real_client(client_ip="2001:db8:1:3::1")
    assert await _attempt(neighbour, real_db.member_email, PASSWORD) == 200
    # The audit log keeps the full address, not the prefix.
    me = (await neighbour.get("/api/auth/me")).json()["user"]
    body = {"locale": "en", "version": me["version"]}
    assert (await neighbour.patch("/api/auth/me", json=body)).status_code == 200
    async with real_db.database.session_factory() as s:
        assert await s.scalar(select(AuditLog.ip)) == "2001:db8:1:3::1"


async def test_failures_from_one_ipv6_prefix_lock_the_account_for_the_prefix(
    real_db: RealDb, real_app: FastAPI, make_real_client: MakeRealClient
) -> None:
    _limits(real_app, account=2)
    for host in ("a", "b"):
        client = await make_real_client(client_ip=f"2001:db8:5:6::{host}")
        assert await _attempt(client, real_db.member_email, "wrong-password") == 401
    rotated = await make_real_client(client_ip="2001:db8:5:6:ffff::1")
    assert await _attempt(rotated, real_db.member_email, PASSWORD) == 429


@pytest.mark.parametrize(
    ("address", "key"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("2001:db8:1:2:3:4:5:6", "2001:db8:1:2::/64"),
        ("2001:DB8:1:2::1", "2001:db8:1:2::/64"),
        ("::ffff:203.0.113.7", "203.0.113.7"),
        (None, "unknown"),
        ("not-an-address", "not-an-address"),
    ],
)
def test_limit_key_of_an_address(address: str | None, key: str) -> None:
    assert limit_key(address) == key


async def test_attempts_in_flight_are_waited_for_then_decided(real_db: RealDb) -> None:
    """Reservations that never end (their request died) count once the wait is over."""
    key = "login-fail:x:wait@example.com"
    async with real_db.database.session_factory() as s:
        s.add_all(RateLimitHit(key=PENDING + key, hit_at=utcnow()) for _ in range(2))
        await s.commit()
        assert await FailureLimiter(s, key, limit=3).begin() is not None
        started = time.monotonic()
        assert await FailureLimiter(s, key, limit=3, max_wait=0.2).begin() is None
        assert time.monotonic() - started >= 0.2
        assert not s.in_transaction()  # nothing held after deciding
