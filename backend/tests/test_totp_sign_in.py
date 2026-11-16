"""Signing in with TOTP (plan M9 task 16): the password step opens no session, a
short-lived, single-use waiting sign-in bound to a cookie does; the second step with
a code or a recovery code opens it."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth.models import UserSession
from app.modules.totp.models import SignInChallenge
from app.modules.totp.challenges import CHALLENGE_MINUTES, MAX_CHALLENGE_FAILURES
from app.modules.users.models import User
from tests.conftest import MakeClient, json_lines
from tests.factories import CSRF, PASSWORD
from tests.factories_totp import TOTP, Enrolled, enroll
from tests.support.clock import SettableClock

LOGIN = "/api/auth/login"
SECOND = "/api/auth/login/second-factor"


@pytest.fixture
async def enrolled(member_client: AsyncClient, member: User, totp_time: SettableClock) -> Enrolled:
    return await enroll(member_client, totp_time)


async def _password(client: AsyncClient, user: User) -> dict[str, object]:
    r = await client.post(LOGIN, json={"email": user.email, "password": PASSWORD}, headers=CSRF)
    assert r.status_code == 202, r.text
    return dict(r.json())


async def _sessions(session: AsyncSession, user: User) -> int:
    rows = await session.scalars(select(UserSession).where(UserSession.user_id == user.id))
    return len(rows.all())


async def test_the_password_alone_opens_no_session(
    make_client: MakeClient, member: User, enrolled: Enrolled, session: AsyncSession
) -> None:
    browser = await make_client(csrf=True)
    before = await _sessions(session, member)
    body = await _password(browser, member)
    assert body["second_factor"] == "totp"
    assert await _sessions(session, member) == before
    assert (await browser.get("/api/auth/me")).status_code == 401
    challenge = (await session.scalars(select(SignInChallenge))).one()
    assert challenge.user_id == member.id and challenge.method == "password"
    cookie = browser.cookies.get("herd_sign_in")
    assert cookie and challenge.token_hash != cookie  # only the hash is stored


async def test_the_challenge_cookie_is_httponly_and_short_lived(
    make_client: MakeClient, member: User, enrolled: Enrolled
) -> None:
    browser = await make_client(csrf=True)
    body = {"email": member.email, "password": PASSWORD}
    r = await browser.post(LOGIN, json=body, headers=CSRF)
    cookie = r.headers["set-cookie"].lower()
    assert cookie.startswith("herd_sign_in=") and "httponly" in cookie
    assert "path=/api/auth" in cookie and f"max-age={CHALLENGE_MINUTES * 60}" in cookie
    https = await browser.post("https://test" + LOGIN, json=body, headers=CSRF)
    assert https.status_code == 202
    secure = https.headers["set-cookie"].lower()
    assert secure.startswith("__host-herd_sign_in=") and "secure" in secure and "path=/;" in secure


async def test_the_code_opens_the_session(
    make_client: MakeClient, member: User, enrolled: Enrolled
) -> None:
    browser = await make_client(csrf=True)
    await _password(browser, member)
    r = await browser.post(SECOND, json={"code": enrolled.next_code()})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["id"] == str(member.id)
    assert (await browser.get("/api/auth/me")).status_code == 200
    assert "herd_sign_in=" in r.headers.get("set-cookie", "")  # cleared


async def test_a_recovery_code_opens_the_session_once(
    make_client: MakeClient, member: User, enrolled: Enrolled
) -> None:
    code = enrolled.recovery_codes[0]
    first = await make_client(csrf=True)
    await _password(first, member)
    assert (await first.post(SECOND, json={"recovery_code": code})).status_code == 200
    second = await make_client(csrf=True)
    await _password(second, member)
    r = await second.post(SECOND, json={"recovery_code": code})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.second_factor_invalid"


async def test_a_challenge_is_used_once(
    make_client: MakeClient, member: User, enrolled: Enrolled, session: AsyncSession
) -> None:
    browser = await make_client(csrf=True)
    await _password(browser, member)
    cookie = browser.cookies.get("herd_sign_in")
    assert (await browser.post(SECOND, json={"code": enrolled.next_code()})).status_code == 200
    again = await make_client(csrf=True)
    again.cookies.set("herd_sign_in", str(cookie))
    r = await again.post(SECOND, json={"code": enrolled.next_code()})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.second_factor_expired"
    assert (await session.scalars(select(SignInChallenge))).all() == []


async def test_without_the_cookie_there_is_nothing_to_finish(
    make_client: MakeClient, member: User, enrolled: Enrolled
) -> None:
    await _password(await make_client(csrf=True), member)
    other_browser = await make_client(csrf=True)
    r = await other_browser.post(SECOND, json={"code": enrolled.next_code()})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.second_factor_expired"


async def test_a_challenge_expires(
    make_client: MakeClient, member: User, enrolled: Enrolled
) -> None:
    browser = await make_client(csrf=True)
    await _password(browser, member)
    enrolled.clock.advance(timedelta(minutes=CHALLENGE_MINUTES, seconds=1))
    r = await browser.post(SECOND, json={"code": enrolled.code()})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.second_factor_expired"


async def test_a_used_step_is_refused_at_sign_in(
    make_client: MakeClient, member: User, enrolled: Enrolled
) -> None:
    browser = await make_client(csrf=True)
    await _password(browser, member)
    r = await browser.post(SECOND, json={"code": enrolled.code()})  # the confirming code
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.second_factor_invalid"


async def test_codes_outside_the_window_are_refused(
    make_client: MakeClient, member: User, enrolled: Enrolled
) -> None:
    browser = await make_client(csrf=True)
    await _password(browser, member)
    enrolled.clock.advance(timedelta(minutes=2))
    for steps in (-2, 2):
        r = await browser.post(SECOND, json={"code": enrolled.code(steps)})
        assert r.status_code == 401, steps
    assert (await browser.post(SECOND, json={"code": enrolled.code(1)})).status_code == 200


async def test_wrong_codes_end_the_challenge(
    make_client: MakeClient, member: User, enrolled: Enrolled, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "login_rate_limit_per_minute", 100)
    browser = await make_client(csrf=True)
    await _password(browser, member)
    for _ in range(MAX_CHALLENGE_FAILURES):
        r = await browser.post(SECOND, json={"code": "000000"})
        assert r.json()["error"]["code"] == "auth.second_factor_invalid"
    r = await browser.post(SECOND, json={"code": enrolled.next_code()})
    assert r.json()["error"]["code"] == "auth.second_factor_expired"


async def test_wrong_codes_count_per_person_across_challenges(
    make_client: MakeClient, member: User, enrolled: Enrolled
) -> None:
    limit = get_settings().login_rate_limit_per_minute
    for _ in range(limit):
        browser = await make_client(csrf=True)
        await _password(browser, member)
        assert (await browser.post(SECOND, json={"code": "000000"})).status_code == 401
    browser = await make_client(csrf=True)
    await _password(browser, member)
    r = await browser.post(SECOND, json={"code": enrolled.next_code()})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "auth.too_many_attempts"


async def test_a_deactivated_person_cannot_finish(
    make_client: MakeClient, member: User, enrolled: Enrolled, owner: AsyncClient
) -> None:
    browser = await make_client(csrf=True)
    await _password(browser, member)
    assert (await owner.post(f"/api/admin/users/{member.id}/deactivate")).status_code == 204
    r = await browser.post(SECOND, json={"code": enrolled.next_code()})
    assert r.status_code == 401


async def test_ending_the_persons_sessions_ends_waiting_sign_ins(
    make_client: MakeClient,
    member: User,
    enrolled: Enrolled,
    owner: AsyncClient,
    session: AsyncSession,
) -> None:
    browser = await make_client(csrf=True)
    await _password(browser, member)
    assert (await owner.post(f"/api/admin/users/{member.id}/sign-out")).status_code == 204
    assert (await session.scalars(select(SignInChallenge))).all() == []
    r = await browser.post(SECOND, json={"code": enrolled.next_code()})
    assert r.json()["error"]["code"] == "auth.second_factor_expired"


async def test_a_wrong_password_never_reaches_the_second_step(
    make_client: MakeClient, member: User, enrolled: Enrolled, session: AsyncSession
) -> None:
    browser = await make_client(csrf=True)
    body = {"email": member.email, "password": "wrong-password-1"}
    r = await browser.post(LOGIN, json=body, headers=CSRF)
    assert r.status_code == 401
    assert (await session.scalars(select(SignInChallenge))).all() == []


async def test_without_totp_the_password_signs_in_as_before(
    make_client: MakeClient, owner_user: User, enrolled: Enrolled
) -> None:
    browser = await make_client(csrf=True)
    body = {"email": owner_user.email, "password": PASSWORD}
    assert (await browser.post(LOGIN, json=body, headers=CSRF)).status_code == 200


async def test_both_steps_are_logged_without_secrets(
    make_client: MakeClient, member: User, enrolled: Enrolled, capsys
) -> None:
    browser = await make_client(csrf=True)
    capsys.readouterr()
    await _password(browser, member)
    await browser.post(SECOND, json={"code": "000000"})
    code = enrolled.next_code()
    await browser.post(SECOND, json={"code": code})
    out = capsys.readouterr().out
    for secret in (code, enrolled.secret, PASSWORD, member.email, str(browser.cookies)):
        assert secret not in out
    events = [e for e in json_lines(out) if e.get("message") == "auth.sign_in"]
    assert [(e["method"], e["outcome"]) for e in events] == [
        ("password", "second_factor"),
        ("second_factor", "second_factor_invalid"),
        ("password+totp", "ok"),
    ]
    assert events[2]["user_id"] == str(member.id)
