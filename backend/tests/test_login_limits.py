"""Login rate limits under real concurrency (real commits, separate connections).

- Per client address and email only failures count, and the count is atomic.
- Per client address all attempts count, whatever the email (bounds password hashing).
- Someone at another address cannot lock a person out.
- Stale counters of any key are pruned.
"""

import asyncio
from datetime import timedelta

from fastapi import FastAPI
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.core.models_base import utcnow
from app.core.ratelimit import PRUNE_BATCH, WINDOW, RateLimitHit
from tests.factories import CSRF, PASSWORD
from tests.real_db import MakeRealClient, RealDb


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
