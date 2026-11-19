"""A lasting lock on the second factor (review M9b F9): the per-minute limit alone let
someone with the password try some 7,200 codes a day. After LOCK_AFTER wrong codes
within LOCK_WINDOW the second factor refuses everything for LOCK_FOR (429
`auth.second_factor_locked`, even a correct code), audited as `user.totp_locked`, and
the person finds a notification in her activity; a correct code resets the count."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.audit.models import AuditLog
from app.modules.totp.challenges import MAX_CHALLENGE_FAILURES
from app.modules.totp.factor import LOCK_AFTER, LOCK_FOR, LOCK_WINDOW
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories import CSRF, PASSWORD
from tests.factories_totp import Enrolled, enroll
from tests.support.clock import SettableClock

LOGIN = "/api/auth/login"
SECOND = "/api/auth/login/second-factor"


@pytest.fixture
async def enrolled(
    member_client: AsyncClient,
    member: User,
    totp_time: SettableClock,
    monkeypatch: pytest.MonkeyPatch,
) -> Enrolled:
    monkeypatch.setattr(get_settings(), "login_rate_limit_per_minute", 1000)
    monkeypatch.setattr(get_settings(), "login_ip_rate_limit_per_minute", 1000)
    return await enroll(member_client, totp_time)


async def _second(make_client: MakeClient, member: User, codes: list[str]) -> list[dict]:  # type: ignore[type-arg]
    """A password step, then `codes` as second steps (new sign-ins as needed)."""
    answers = []
    browser = None
    for index, code in enumerate(codes):
        if index % MAX_CHALLENGE_FAILURES == 0:
            browser = await make_client(csrf=True)
            body = {"email": member.email, "password": PASSWORD}
            assert (await browser.post(LOGIN, json=body, headers=CSRF)).status_code == 202
        assert browser is not None
        r = await browser.post(SECOND, json={"code": code})
        answers.append({"status": r.status_code, **r.json()})
    return answers


def _code(answer: dict) -> str:  # type: ignore[type-arg]
    return str(answer.get("error", {}).get("code"))


async def test_ten_wrong_codes_lock_the_second_factor_for_an_hour(
    make_client: MakeClient,
    member: User,
    member_client: AsyncClient,
    enrolled: Enrolled,
    session: AsyncSession,
) -> None:
    assert (LOCK_AFTER, LOCK_WINDOW, LOCK_FOR) == (10, timedelta(hours=24), timedelta(hours=1))
    wrong = await _second(make_client, member, ["000000"] * LOCK_AFTER)
    assert [_code(a) for a in wrong] == ["auth.second_factor_invalid"] * LOCK_AFTER

    (locked,) = await _second(make_client, member, [enrolled.next_code()])
    assert (locked["status"], _code(locked)) == (429, "auth.second_factor_locked")
    audit = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "user.totp_locked"))
    ).one()
    assert audit.target_id == member.id and audit.actor_type == "system"
    activity = (await member_client.get("/api/activity")).json()["items"]
    assert [(e["reason"], e["account"]["id"]) for e in activity] == [
        ("totp_locked", str(member.id))
    ]

    enrolled.clock.advance(LOCK_FOR)
    (passed,) = await _second(make_client, member, [enrolled.next_code()])
    assert passed["status"] == 200, passed


async def test_a_correct_code_resets_the_count(
    make_client: MakeClient, member: User, enrolled: Enrolled
) -> None:
    await _second(make_client, member, ["000000"] * (LOCK_AFTER - 1))
    assert (await _second(make_client, member, [enrolled.next_code()]))[0]["status"] == 200
    answers = await _second(make_client, member, ["000000"] * (LOCK_AFTER - 1))
    assert {_code(a) for a in answers} == {"auth.second_factor_invalid"}
    assert (await _second(make_client, member, [enrolled.next_code()]))[0]["status"] == 200


async def test_wrong_codes_older_than_the_window_do_not_count(
    make_client: MakeClient, member: User, enrolled: Enrolled
) -> None:
    await _second(make_client, member, ["000000"] * (LOCK_AFTER - 1))
    enrolled.clock.advance(LOCK_WINDOW + timedelta(minutes=1))
    answers = await _second(make_client, member, ["000000"] * 2)
    assert {_code(a) for a in answers} == {"auth.second_factor_invalid"}
    assert (await _second(make_client, member, [enrolled.next_code()]))[0]["status"] == 200
