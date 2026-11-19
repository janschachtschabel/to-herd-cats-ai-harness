"""A person sees her own login sessions and ends one or all others (ASVS 5.0 V7.5.2,
plan M9 task 18, J8)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.audit.models import AuditLog
from app.modules.auth.device import device_hint
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories import login

SESSIONS = "/api/auth/me/sessions"
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0"
SAFARI = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15"
    " (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
)


async def _signed_in(make_client: MakeClient, email: str, agent: str) -> AsyncClient:
    client = await make_client(csrf=True)
    client.headers["User-Agent"] = agent
    await login(client, email)
    return client


async def test_own_sessions_list_and_end_one(
    make_client: MakeClient, owner_user: User, session: AsyncSession
) -> None:
    laptop = await _signed_in(make_client, owner_user.email, FIREFOX)
    phone = await _signed_in(make_client, owner_user.email, SAFARI)
    listed = await laptop.get(SESSIONS)
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert [(item["device"], item["current"]) for item in items] == [
        ("Safari · iOS", False),
        ("Firefox · Linux", True),
    ]
    assert all(item["signed_in_at"] and item["last_used_at"] for item in items)
    assert set(items[0]) == {"id", "device", "signed_in_at", "last_used_at", "current"}

    ended = await laptop.delete(f"{SESSIONS}/{items[0]['id']}")
    assert ended.status_code == 204
    gone = await phone.get("/api/auth/me")
    assert gone.status_code == 401
    assert [item["current"] for item in (await laptop.get(SESSIONS)).json()["items"]] == [True]
    audit = await session.scalar(select(AuditLog).where(AuditLog.action == "user.session_ended"))
    assert audit is not None and audit.target_id == owner_user.id
    assert audit.details == {"session_id": items[0]["id"]}


async def test_another_persons_session_answers_404(
    make_client: MakeClient, owner_user: User, member: User
) -> None:
    owner = await _signed_in(make_client, owner_user.email, FIREFOX)
    other = await _signed_in(make_client, member.email, SAFARI)
    theirs = (await other.get(SESSIONS)).json()["items"][0]["id"]
    for target in (theirs, str(uuid.uuid4())):
        refused = await owner.delete(f"{SESSIONS}/{target}")
        assert refused.status_code == 404
        assert refused.json()["error"]["code"] == "auth.session_not_found"
    assert (await other.get("/api/auth/me")).status_code == 200


async def test_signing_out_the_others_keeps_this_one(
    make_client: MakeClient, owner_user: User
) -> None:
    here = await _signed_in(make_client, owner_user.email, FIREFOX)
    others = [await _signed_in(make_client, owner_user.email, SAFARI) for _ in range(2)]
    answer = await here.post(f"{SESSIONS}/sign-out-others")
    assert answer.status_code == 204
    for other in others:
        assert (await other.get("/api/auth/me")).status_code == 401
    assert (await here.get("/api/auth/me")).status_code == 200
    assert len((await here.get(SESSIONS)).json()["items"]) == 1


async def test_the_list_is_paginated(make_client: MakeClient, owner_user: User) -> None:
    here = await _signed_in(make_client, owner_user.email, FIREFOX)
    for _ in range(2):
        await _signed_in(make_client, owner_user.email, SAFARI)
    first = (await here.get(SESSIONS, params={"limit": 2})).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = (await here.get(SESSIONS, params={"limit": 2, "cursor": first["next_cursor"]})).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    assert rest["items"][0]["current"] is True
    assert (await here.get(SESSIONS, params={"limit": 101})).status_code == 422


@pytest.mark.parametrize(
    ("agent", "hint"),
    [
        (FIREFOX, "Firefox · Linux"),
        (SAFARI, "Safari · iOS"),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
            " Chrome/131.0.0.0 Safari/537.36 Edg/131.0.2903.86",
            "Edge · Windows",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like"
            " Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Chrome · macOS",
        ),
        (
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko)"
            " Chrome/131.0.0.0 Mobile Safari/537.36",
            "Chrome · Android",
        ),
        ("curl/8.5.0", "curl"),
        ("python-httpx/0.28.1", "python-httpx"),
        ("", None),
        (None, None),
        ("x" * 500 + "/1.0", "x" * 40),
    ],
)
def test_the_device_hint_names_browser_and_system_without_versions(
    agent: str | None, hint: str | None
) -> None:
    assert device_hint(agent) == hint


async def test_signing_out_the_others_counts_only_running_sessions(
    make_client: MakeClient, owner_user: User, session: AsyncSession
) -> None:
    """A session already ended (signed out, not yet cleared away) is no session ended
    now (R18-11)."""
    here = await _signed_in(make_client, owner_user.email, FIREFOX)
    gone = await _signed_in(make_client, owner_user.email, SAFARI)
    await _signed_in(make_client, owner_user.email, SAFARI)
    assert (await gone.post("/api/auth/logout")).status_code == 204
    assert (await here.post(f"{SESSIONS}/sign-out-others")).status_code == 204
    audit = await session.scalar(select(AuditLog).where(AuditLog.action == "user.session_ended"))
    assert audit is not None and audit.details == {"others": 1}


@pytest.mark.parametrize(("idle", "expected"), [(24, 24), (0, None)])
async def test_me_names_the_session_limits(
    make_client: MakeClient,
    owner_user: User,
    monkeypatch: pytest.MonkeyPatch,
    idle: int,
    expected: int | None,
) -> None:
    """The sessions list says the installation's limits, not fixed numbers (R18-11)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "session_idle_hours", idle)
    here = await _signed_in(make_client, owner_user.email, FIREFOX)
    limits = (await here.get("/api/auth/me")).json()["session_limits"]
    assert limits == {"idle_hours": expected, "ttl_hours": settings.session_ttl_hours}
