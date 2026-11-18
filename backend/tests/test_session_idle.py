"""A login session ends after HERD_SESSION_IDLE_HOURS without use (ASVS 5.0 V7.3.1,
plan M9 task 18, J7); its last use is written at most once a minute."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth.models import UserSession
from app.modules.users.models import User
from tests.factories import login
from tests.support.clock import SettableClock


async def _last_used(session: AsyncSession, user: User) -> object:
    stmt = select(UserSession.last_used_at).where(UserSession.user_id == user.id)
    return await session.scalar(stmt)


async def test_an_idle_session_ends_after_the_idle_hours(
    client: AsyncClient,
    owner_user: User,
    session_time: SettableClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "session_idle_hours", 24)
    await login(client, owner_user.email)
    session_time.advance(timedelta(hours=23, minutes=59))
    assert (await client.get("/api/auth/me")).status_code == 200  # used: counts again
    session_time.advance(timedelta(hours=23, minutes=59))
    assert (await client.get("/api/auth/me")).status_code == 200
    session_time.advance(timedelta(hours=24, minutes=1))
    idle = await client.get("/api/auth/me")
    assert idle.status_code == 401
    assert idle.json()["error"]["code"] == "auth.session_invalid"


async def test_no_idle_limit_with_zero_hours(
    client: AsyncClient,
    owner_user: User,
    session_time: SettableClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "session_idle_hours", 0)
    await login(client, owner_user.email)
    session_time.advance(timedelta(days=6))
    assert (await client.get("/api/auth/me")).status_code == 200
    session_time.advance(timedelta(days=1, minutes=1))  # the absolute limit still holds
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_last_used_is_written_at_most_once_a_minute(
    client: AsyncClient,
    session: AsyncSession,
    owner_user: User,
    session_time: SettableClock,
) -> None:
    signed_in = session_time.now()
    await login(client, owner_user.email)
    assert await _last_used(session, owner_user) == signed_in
    session_time.advance(timedelta(seconds=59))
    assert (await client.get("/api/auth/me")).status_code == 200
    assert await _last_used(session, owner_user) == signed_in
    session_time.advance(timedelta(seconds=1))
    assert (await client.get("/api/auth/me")).status_code == 200
    assert await _last_used(session, owner_user) == session_time.now()


async def test_the_live_stream_is_no_use(
    client: AsyncClient,
    session: AsyncSession,
    owner_user: User,
    session_time: SettableClock,
) -> None:
    """Opening the live stream checks the session but does not keep it alive."""
    signed_in = session_time.now()
    await login(client, owner_user.email)
    session_time.advance(timedelta(minutes=5))
    await client.get("/api/stream")  # 503 here (no hub): the session was checked
    assert await _last_used(session, owner_user) == signed_in
