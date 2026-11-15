"""OIDC fixtures: `oidc_stub` (a local OpenID provider, https for `idp.test`, reset per
test), `oidc_egress` (the egress guard resolving `*.test` to 127.0.0.1 and trusting
the stub's certificate), plus helpers to set up a provider through the API and to sign
in through it like a browser."""

import ipaddress
import ssl
from collections.abc import Iterator
from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.core import egress
from app.core.egress import Network
from tests.factories import CSRF
from tests.factories_mcp import resolve_test_names
from tests.support.oidc_stub import OidcStub

PROVIDERS = "/api/admin/oidc-providers"
SECRET_ENV = "HERD_OIDC_STUB_SECRET"


@pytest.fixture(scope="session")
def _oidc_stub() -> Iterator[OidcStub]:
    stub = OidcStub().start()
    yield stub
    stub.stop()


@pytest.fixture
def oidc_stub(_oidc_stub: OidcStub) -> Iterator[OidcStub]:
    _oidc_stub.state.reset()
    yield _oidc_stub
    _oidc_stub.state.reset()


@pytest.fixture
def oidc_egress(oidc_stub: OidcStub, public_url: str, monkeypatch: pytest.MonkeyPatch) -> OidcStub:
    """The stub reachable through the egress guard, its secret in the environment and
    the public address set (the redirect URI is derived from it)."""
    network = Network(
        resolver=resolve_test_names,
        ssl_context=ssl.create_default_context(cafile=str(oidc_stub.cert_path)),
        extra_allowed=(ipaddress.ip_network("127.0.0.1/32"),),
    )
    monkeypatch.setattr(egress, "_network", network)
    monkeypatch.setenv(SECRET_ENV, oidc_stub.state.client_secret)
    return oidc_stub


async def make_provider(owner: AsyncClient, stub: OidcStub, **fields: Any) -> dict[str, Any]:
    """A generic provider for the stub, switched on; `fields` override."""
    body: dict[str, Any] = {
        "kind": "generic",
        "key": "stub",
        "name": "Stub IdP",
        "issuer": stub.url,
        "client_id": stub.state.client_id,
        "client_secret": {"env": SECRET_ENV},
        "enabled": True,
        **fields,
    }
    response = await owner.post(PROVIDERS, json=body)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def start(browser: AsyncClient, key: str = "stub") -> Response:
    return await browser.get(f"/api/auth/oidc/{key}/start")


async def sign_in(
    browser: AsyncClient, stub: OidcStub, key: str = "stub", **identity: Any
) -> Response:
    """Start, approve at the stub as `identity`, and come back; the callback's answer."""
    if identity:
        stub.state.identity = {**stub.state.identity, **identity}
    started = await start(browser, key)
    assert started.status_code == 302, started.text
    query = stub.state.authorize(started.headers["location"])
    return await browser.get(f"/api/auth/oidc/{key}/callback", params=query)


def error_of(response: Response) -> str | None:
    """The `error` of a redirect to the sign-in page (None if it is not one)."""
    from urllib.parse import parse_qs, urlsplit  # noqa: PLC0415

    location = urlsplit(response.headers.get("location", ""))
    values = parse_qs(location.query).get("error") or parse_qs(location.query).get("link_error")
    return values[0] if values else None


__all__ = ["CSRF", "make_provider", "sign_in", "start", "error_of"]
