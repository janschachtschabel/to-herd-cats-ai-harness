"""The Google preset, the JWKS refetch and the egress guard for OIDC (plan M9 task 4)."""

import logging
import ssl
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as clocks
from app.core import egress
from app.core.config import get_settings
from app.core.egress import Network
from app.core.models_base import utcnow
from app.modules.oidc.models import OidcProvider
from tests.conftest import MakeClient
from tests.factories_mcp import resolve_test_names
from tests.factories_oidc import PROVIDERS, SECRET_ENV, error_of, make_provider, sign_in, start
from tests.support.clock import SettableClock
from tests.support.oidc_stub import OidcStub

pytestmark = pytest.mark.usefixtures("oidc_egress")


async def _google(
    owner: AsyncClient, stub: OidcStub, session: AsyncSession, **fields: Any
) -> dict[str, Any]:
    """The Google preset, its endpoints pointed at the stub (accounts.google.com is
    never dialled in tests)."""
    body = {
        "kind": "google",
        "client_id": stub.state.client_id,
        "client_secret": {"env": SECRET_ENV},
        "enabled": True,
        **fields,
    }
    response = await owner.post(PROVIDERS, json=body)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    await session.execute(
        update(OidcProvider)
        .where(OidcProvider.key == "google")
        .values(
            authorization_endpoint=f"{stub.url}/authorize",
            token_endpoint=f"{stub.url}/token",
            jwks_uri=f"{stub.url}/jwks",
        )
    )
    return created


def _query(location: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}


async def test_google_preset_sends_hd_only_with_exactly_one_domain_and_accepts_both_issuers(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub, session: AsyncSession
) -> None:
    created = await _google(
        owner, oidc_stub, session, allow_signup=True, allowed_domains=["example.com"]
    )
    assert created["issuer"] == "https://accounts.google.com"
    assert created["scopes"] == "openid email profile"
    assert created["name"] == "Google" and created["key"] == "google"
    query = _query((await start(await make_client(), "google")).headers["location"])
    assert query["hd"] == "example.com" and query["prompt"] == "select_account"
    oidc_stub.state.issuer_claim = "accounts.google.com"
    done = await sign_in(
        await make_client(), oidc_stub, "google", email="a@example.com", hd="example.com", sub="g1"
    )
    assert done.headers["location"] == "/", done.headers
    oidc_stub.state.issuer_claim = "https://accounts.google.com"
    done = await sign_in(await make_client(), oidc_stub, "google", sub="g1")
    assert done.headers["location"] == "/"
    oidc_stub.state.issuer_claim = oidc_stub.url  # not Google's
    done = await sign_in(await make_client(), oidc_stub, "google", sub="g1")
    assert error_of(done) == "oidc.id_token_invalid"
    version = created["version"]
    for domains in (["example.com", "example.org"], ["gmail.com"]):
        patched = await owner.patch(
            f"{PROVIDERS}/{created['id']}", json={"version": version, "allowed_domains": domains}
        )
        assert patched.status_code == 200, patched.text
        version = patched.json()["version"]
        query = _query((await start(await make_client(), "google")).headers["location"])
        assert "hd" not in query and query["prompt"] == "select_account"


async def test_google_refuses_a_foreign_address_without_hd(
    owner: AsyncClient,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    session: AsyncSession,
    member: Any,
) -> None:
    """A Google account with someone's company address but no `hd` (a consumer account
    on a foreign address) neither links nor signs up."""
    await _google(owner, oidc_stub, session, allow_signup=True, allowed_domains=["example.com"])
    oidc_stub.state.issuer_claim = "https://accounts.google.com"
    done = await sign_in(await make_client(), oidc_stub, "google", email=member.email)
    assert error_of(done) == "oidc.link_refused"
    done = await sign_in(await make_client(), oidc_stub, "google", email="new@example.com")
    assert error_of(done) == "oidc.domain_not_allowed"


async def test_a_new_kid_refetches_jwks_at_most_once_a_minute(
    owner: AsyncClient,
    member: Any,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = SettableClock(utcnow())
    monkeypatch.setattr(clocks, "SYSTEM_CLOCK", clock)
    await make_provider(owner, oidc_stub, trust_email=True)
    identity = {"email": member.email}
    assert (await sign_in(await make_client(), oidc_stub, **identity)).headers["location"] == "/"
    assert len(oidc_stub.state.requests("/jwks")) == 1
    oidc_stub.state.rotate()  # signs with a key the JWKS does not show yet
    done = await sign_in(await make_client(), oidc_stub, **identity)
    assert error_of(done) == "oidc.id_token_invalid"
    assert len(oidc_stub.state.requests("/jwks")) == 1  # fetched within the minute: not again
    clock.advance(timedelta(seconds=61))
    oidc_stub.state.publish_rotated()
    done = await sign_in(await make_client(), oidc_stub, **identity)
    assert done.headers["location"] == "/"
    assert len(oidc_stub.state.requests("/jwks")) == 2
    for _ in range(3):  # a stream of unknown kids fetches nothing more within the minute
        done = await sign_in(await make_client(), oidc_stub, **identity)
    assert len(oidc_stub.state.requests("/jwks")) == 2


async def test_discovery_and_jwks_go_through_the_egress_guard(
    owner: AsyncClient,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`idp.test` resolves to 127.0.0.1: refused until the operator lists it."""
    guarded = Network(
        resolver=resolve_test_names,
        ssl_context=ssl.create_default_context(cafile=str(oidc_stub.cert_path)),
    )
    monkeypatch.setattr(egress, "_network", guarded)
    created = await make_provider(owner, oidc_stub)
    check = await owner.post(f"{PROVIDERS}/{created['id']}/check")
    assert check.json() == {"ok": False, "code": "oidc.provider_unreachable"}
    assert error_of(await start(await make_client())) == "oidc.provider_unreachable"
    assert oidc_stub.state.log == []
    monkeypatch.setattr(get_settings(), "oidc_allowed_hosts", "idp.test")
    check = await owner.post(f"{PROVIDERS}/{created['id']}/check")
    assert check.json() == {"ok": True, "code": None}
    assert len(oidc_stub.state.requests("/jwks")) == 1


async def test_an_issuer_the_discovery_document_does_not_name_is_refused(
    owner: AsyncClient, oidc_stub: OidcStub
) -> None:
    created = await make_provider(owner, oidc_stub)
    oidc_stub.state.discovery_issuer = "https://elsewhere.test"
    check = await owner.post(f"{PROVIDERS}/{created['id']}/check")
    assert check.json() == {"ok": False, "code": "oidc.issuer_mismatch"}


async def test_no_email_or_claims_in_logs(
    owner: AsyncClient,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await make_provider(owner, oidc_stub, allow_signup=True, allowed_domains=["geheim.example"])
    caplog.set_level(logging.DEBUG)
    secret_bits = ("lena@geheim.example", "Lena Leise", "sub-lena-77", "geheim.example")
    browser = await make_client()
    started = await start(browser)
    query = {**oidc_stub.state.authorize(started.headers["location"])}
    oidc_stub.state.codes[query["code"]].claims.update(
        email=secret_bits[0], name=secret_bits[1], sub=secret_bits[2]
    )
    done = await browser.get("/api/auth/oidc/stub/callback", params=query)
    assert done.headers["location"] == "/"
    oidc_stub.state.token_claims = {"aud": "wrong"}
    await sign_in(await make_client(), oidc_stub, email=secret_bits[0])
    ours = [r for r in caplog.records if not r.name.startswith("uvicorn")]
    text = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in ours) + capsys.readouterr().out
    for bit in (*secret_bits, query["code"], query["state"], browser.cookies["herd_session"]):
        assert bit not in text, bit
    assert "oidc id token refused" in text  # the refusal is logged, by its reason only
