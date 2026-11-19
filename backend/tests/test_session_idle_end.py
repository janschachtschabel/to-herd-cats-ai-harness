"""An idle end is recorded on the session's row, like a sign-out, so a longer or no idle
limit later does not revive the session (review M9b Task 18, R18-3)."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth.models import UserSession
from app.modules.users.models import User
from app.worker.upkeep import end_idle_sessions
from tests.factories import login
from tests.support.clock import SettableClock


async def _expires(session: AsyncSession, user: User) -> object:
    stmt = select(UserSession.expires_at).where(UserSession.user_id == user.id)
    return await session.scalar(stmt.execution_options(populate_existing=True))


async def test_a_request_records_the_idle_end(
    client: AsyncClient,
    session: AsyncSession,
    owner_user: User,
    session_time: SettableClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "session_idle_hours", 24)
    signed_in = session_time.now()
    await login(client, owner_user.email)
    session_time.advance(timedelta(hours=30))
    assert (await client.get("/api/auth/me")).status_code == 401
    assert await _expires(session, owner_user) == signed_in + timedelta(hours=24)
    monkeypatch.setattr(settings, "session_idle_hours", 0)  # the operator lifts the limit
    assert (await client.get("/api/auth/me")).status_code == 401
    monkeypatch.setattr(settings, "session_idle_hours", 48)
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_a_logout_with_an_idle_ended_cookie_ends_the_row(
    client: AsyncClient,
    session: AsyncSession,
    owner_user: User,
    session_time: SettableClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "session_idle_hours", 24)
    await login(client, owner_user.email)
    session_time.advance(timedelta(hours=30))
    # The cookie is still in the browser: the sign-out is the first request after.
    await client.post("/api/auth/logout", headers={"X-Requested-With": "herd"})
    expires = await _expires(session, owner_user)
    assert expires is not None and expires <= session_time.now()  # type: ignore[operator]
    monkeypatch.setattr(settings, "session_idle_hours", 0)
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_the_upkeep_records_the_idle_end_of_a_session_nobody_comes_back_to(
    client: AsyncClient,
    session: AsyncSession,
    owner_user: User,
    session_time: SettableClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "session_idle_hours", 24)
    signed_in = session_time.now()
    await login(client, owner_user.email)
    session_time.advance(timedelta(hours=23))
    assert await end_idle_sessions(session, session_time.now(), 100) == 0
    session_time.advance(timedelta(hours=2))
    assert await end_idle_sessions(session, session_time.now(), 100) == 1
    assert await _expires(session, owner_user) == signed_in + timedelta(hours=24)
    monkeypatch.setattr(settings, "session_idle_hours", 0)
    assert (await client.get("/api/auth/me")).status_code == 401
