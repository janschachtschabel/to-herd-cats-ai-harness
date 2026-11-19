"""Every sign-in, failed or not, and every sign-out is logged (ASVS 5.0 V16.3.1): the
way (`password`, `oidc`), the outcome as a fixed word, the person's id on success and
the client's address; never the email, the password, a token or a claim."""

import pytest
from httpx import AsyncClient

from app.modules.users.models import User
from tests.conftest import MakeClient, json_lines
from tests.factories import CSRF, PASSWORD
from tests.factories_oidc import make_provider, sign_in
from tests.support.oidc_stub import OidcStub


def _events(capsys: pytest.CaptureFixture[str], message: str) -> list[dict[str, object]]:
    out = capsys.readouterr().out
    for secret in (PASSWORD, "wrong-password-1", "owner@example.com"):
        assert secret not in out
    return [line for line in json_lines(out) if line.get("message") == message]


async def test_password_sign_ins_and_sign_outs_are_logged(
    client: AsyncClient, owner_user: User, capsys: pytest.CaptureFixture[str]
) -> None:
    body = {"email": owner_user.email, "password": "wrong-password-1"}
    assert (await client.post("/api/auth/login", json=body, headers=CSRF)).status_code == 401
    body["password"] = PASSWORD
    assert (await client.post("/api/auth/login", json=body, headers=CSRF)).status_code == 200
    events = _events(capsys, "auth.sign_in")
    assert [(e["method"], e["outcome"]) for e in events] == [
        ("password", "invalid_credentials"),
        ("password", "ok"),
    ]
    assert events[0]["level"] == "WARNING" and "user_id" not in events[0]
    assert events[1]["user_id"] == str(owner_user.id) and events[1]["client"]
    assert (await client.post("/api/auth/logout", headers=CSRF)).status_code == 204
    (out,) = _events(capsys, "auth.sign_out")
    assert out["user_id"] == str(owner_user.id)


async def test_a_refused_burst_is_logged_as_rate_limited(
    client: AsyncClient, owner_user: User, capsys: pytest.CaptureFixture[str]
) -> None:
    body = {"email": owner_user.email, "password": "wrong-password-1"}
    for _ in range(6):
        await client.post("/api/auth/login", json=body, headers=CSRF)
    outcomes = [e["outcome"] for e in _events(capsys, "auth.sign_in")]
    assert outcomes[-1] == "too_many_attempts"


@pytest.mark.usefixtures("oidc_egress")
async def test_oidc_sign_ins_are_logged(
    owner: AsyncClient,
    member: User,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await make_provider(owner, oidc_stub, trust_email=True)
    capsys.readouterr()
    await sign_in(await make_client(), oidc_stub, email=member.email, sub="s-log")
    await sign_in(await make_client(), oidc_stub, email="nobody@else.test", sub="s-x")
    events = _events(capsys, "auth.sign_in")
    assert [(e["method"], e["outcome"], e.get("provider")) for e in events] == [
        ("oidc", "link", "stub"),
        ("oidc", "signup_closed", "stub"),
    ]
    assert events[0]["user_id"] == str(member.id)
    assert "s-log" not in str(events) and member.email not in str(events)
