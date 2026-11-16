"""Setting TOTP up in the profile, turning it off, new recovery codes (plan M9 task 16)."""

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.config import get_settings
from app.modules.audit.models import AuditLog
from app.modules.totp.models import TotpRecoveryCode, UserTotp
from app.modules.totp.recovery import digest
from app.modules.users.models import User
from tests.factories import PASSWORD, login
from tests.factories_totp import TOTP, enroll
from tests.support.clock import SettableClock


async def test_nothing_is_set_up_at_first(member_client: AsyncClient, totp_time) -> None:
    r = await member_client.get(TOTP)
    assert r.status_code == 200, r.text
    assert r.json() == {"enabled_at": None, "recovery_codes_left": 0, "unavailable": None}


async def test_setup_needs_the_password(member_client: AsyncClient, totp_time) -> None:
    r = await member_client.post(f"{TOTP}/setup", json={"password": "not-the-password"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "auth.wrong_password"


async def test_setup_shows_the_secret_once_and_stores_it_encrypted(
    member_client: AsyncClient, member: User, session: AsyncSession, totp_time
) -> None:
    r = await member_client.post(f"{TOTP}/setup", json={"password": PASSWORD})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"secret", "uri"}
    assert len(body["secret"]) == 32
    assert body["uri"].startswith("otpauth://totp/Test%20Org:member%40example.com?secret=")
    row = (await session.scalars(select(UserTotp).where(UserTotp.user_id == member.id))).one()
    assert row.secret_ref.startswith("enc:") and body["secret"] not in row.secret_ref
    assert secrets.resolve(row.secret_ref).get_secret_value() == body["secret"]
    assert row.confirmed_at is None
    # Not on yet: the status says so and a sign-in needs no code.
    assert (await member_client.get(TOTP)).json()["enabled_at"] is None
    assert body["secret"] not in (await member_client.get(TOTP)).text


async def test_a_wrong_first_code_does_not_turn_it_on(
    member_client: AsyncClient, totp_time: SettableClock
) -> None:
    await member_client.post(f"{TOTP}/setup", json={"password": PASSWORD})
    r = await member_client.post(f"{TOTP}/confirm", json={"code": "000000"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "auth.second_factor_invalid"
    assert (await member_client.get(TOTP)).json()["enabled_at"] is None


async def test_confirming_turns_it_on_with_ten_hashed_recovery_codes(
    member_client: AsyncClient, member: User, session: AsyncSession, totp_time: SettableClock
) -> None:
    enrolled = await enroll(member_client, totp_time)
    assert len(enrolled.recovery_codes) == 10
    assert len(set(enrolled.recovery_codes)) == 10
    for code in enrolled.recovery_codes:
        assert len(code.replace("-", "")) == 24
    stored = (
        await session.scalars(
            select(TotpRecoveryCode.code_hash).where(TotpRecoveryCode.user_id == member.id)
        )
    ).all()
    assert sorted(stored) == sorted(digest(c) for c in enrolled.recovery_codes)
    status = (await member_client.get(TOTP)).json()
    assert status["enabled_at"] is not None
    assert status["recovery_codes_left"] == 10
    actions = (await session.scalars(select(AuditLog.action))).all()
    assert "user.totp_enabled" in actions
    audit = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "user.totp_enabled"))
    ).one()
    assert audit.details is None


async def test_turning_it_on_ends_other_sessions(
    member: User, make_client, totp_time: SettableClock
) -> None:
    here = await make_client(csrf=True)
    await login(here, member.email)
    elsewhere = await make_client(csrf=True)
    await login(elsewhere, member.email)
    await enroll(here, totp_time)
    assert (await here.get("/api/auth/me")).status_code == 200
    assert (await elsewhere.get("/api/auth/me")).status_code == 401


async def test_setup_again_once_on_is_a_conflict(
    member_client: AsyncClient, totp_time: SettableClock
) -> None:
    await enroll(member_client, totp_time)
    r = await member_client.post(f"{TOTP}/setup", json={"password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "totp.already_enabled"


async def test_a_new_setup_replaces_one_never_confirmed(
    member_client: AsyncClient, member: User, session: AsyncSession, totp_time
) -> None:
    first = (await member_client.post(f"{TOTP}/setup", json={"password": PASSWORD})).json()
    second = (await member_client.post(f"{TOTP}/setup", json={"password": PASSWORD})).json()
    assert first["secret"] != second["secret"]
    rows = (await session.scalars(select(UserTotp).where(UserTotp.user_id == member.id))).all()
    assert len(rows) == 1


async def test_without_a_secret_key_it_is_unavailable(
    member_client: AsyncClient, totp_time, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "secret_key", None)
    assert (await member_client.get(TOTP)).json()["unavailable"] == "no_secret_key"
    r = await member_client.post(f"{TOTP}/setup", json={"password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "totp.no_secret_key"


async def test_without_a_password_it_is_unavailable(
    member_client: AsyncClient, member: User, session: AsyncSession, totp_time
) -> None:
    member.password_hash = None
    await session.flush()
    assert (await member_client.get(TOTP)).json()["unavailable"] == "no_password"
    r = await member_client.post(f"{TOTP}/setup", json={"password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "totp.no_password"


async def test_turning_it_off_needs_a_current_code(
    member_client: AsyncClient, member: User, session: AsyncSession, totp_time: SettableClock
) -> None:
    enrolled = await enroll(member_client, totp_time)
    r = await member_client.post(f"{TOTP}/disable", json={"code": "123456"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "auth.second_factor_invalid"
    r = await member_client.post(f"{TOTP}/disable", json={"code": enrolled.next_code()})
    assert r.status_code == 204, r.text
    assert (await member_client.get(TOTP)).json()["enabled_at"] is None
    assert (
        await session.scalars(select(UserTotp).where(UserTotp.user_id == member.id))
    ).all() == []
    assert (
        await session.scalars(select(TotpRecoveryCode).where(TotpRecoveryCode.user_id == member.id))
    ).all() == []
    actions = (await session.scalars(select(AuditLog.action))).all()
    assert "user.totp_disabled" in actions


async def test_turning_it_off_with_a_recovery_code(
    member_client: AsyncClient, totp_time: SettableClock
) -> None:
    enrolled = await enroll(member_client, totp_time)
    typed = enrolled.recovery_codes[3].lower().replace("-", " ")
    r = await member_client.post(f"{TOTP}/disable", json={"recovery_code": typed})
    assert r.status_code == 204, r.text


async def test_the_code_that_confirmed_cannot_turn_it_off(
    member_client: AsyncClient, totp_time: SettableClock
) -> None:
    enrolled = await enroll(member_client, totp_time)
    r = await member_client.post(f"{TOTP}/disable", json={"code": enrolled.code()})
    assert r.status_code == 422  # the same step is accepted once (V6.5.1)


async def test_an_earlier_step_is_refused_after_a_later_one(
    member_client: AsyncClient, totp_time: SettableClock
) -> None:
    enrolled = await enroll(member_client, totp_time)
    totp_time.advance(timedelta(seconds=30))
    later, earlier = enrolled.code(1), enrolled.code(-1)
    renewed = await member_client.post(f"{TOTP}/recovery-codes", json={"code": later})
    assert renewed.status_code == 200, renewed.text
    r = await member_client.post(f"{TOTP}/disable", json={"code": earlier})
    assert r.status_code == 422


async def test_new_recovery_codes_replace_the_old_ones(
    member_client: AsyncClient, session: AsyncSession, totp_time: SettableClock
) -> None:
    enrolled = await enroll(member_client, totp_time)
    r = await member_client.post(f"{TOTP}/recovery-codes", json={"code": enrolled.next_code()})
    assert r.status_code == 200, r.text
    fresh = r.json()["recovery_codes"]
    assert len(fresh) == 10 and not set(fresh) & set(enrolled.recovery_codes)
    old = await member_client.post(
        f"{TOTP}/disable", json={"recovery_code": enrolled.recovery_codes[0]}
    )
    assert old.status_code == 422
    actions = (await session.scalars(select(AuditLog.action))).all()
    assert "user.totp_recovery_codes_renewed" in actions


async def test_new_recovery_codes_need_a_code_not_a_recovery_code(
    member_client: AsyncClient, totp_time: SettableClock
) -> None:
    enrolled = await enroll(member_client, totp_time)
    r = await member_client.post(
        f"{TOTP}/recovery-codes", json={"recovery_code": enrolled.recovery_codes[0]}
    )
    assert r.status_code == 422


async def test_a_proof_names_exactly_one_kind(
    member_client: AsyncClient, totp_time: SettableClock
) -> None:
    await enroll(member_client, totp_time)
    for body in ({}, {"code": "123456", "recovery_code": "ABC"}, {"code": None}):
        r = await member_client.post(f"{TOTP}/disable", json=body)
        assert r.status_code == 422, body


async def test_wrong_codes_are_limited_per_person(
    member_client: AsyncClient, totp_time: SettableClock
) -> None:
    enrolled = await enroll(member_client, totp_time)
    for _ in range(get_settings().login_rate_limit_per_minute):
        r = await member_client.post(f"{TOTP}/disable", json={"code": "000000"})
        assert r.status_code == 422
    r = await member_client.post(f"{TOTP}/disable", json={"code": enrolled.next_code()})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "auth.too_many_attempts"
