"""Sign-in in the demo (M9), through the public API, only with a stub's address
(`--oidc-stub`, never the outside network by default): a generic OpenID Connect
provider „Demo-Anmeldung" on the stub (`tests/support/oidc_stub.py`), switched on,
with self-registration open for the demo's domain `demo.example`. Whoever signs up
through it lands as a waiting account that an admin approves under Verwaltung →
Personen → Wartet auf Freigabe (plan M9 Task 5b).

The client secret is never in this script: the provider names it as
`env:HERD_OIDC_STUB_SECRET`, which the installation must have (the stub's secret, see
`OidcStubState.client_secret`). The installation also needs `HERD_PUBLIC_URL`, the stub's
host in `HERD_OIDC_ALLOWED_HOSTS` and the stub's certificate trusted (`SSL_CERT_FILE`).
"""

from dataclasses import dataclass

import httpx

from scripts.demo_api import DemoFailed, call

KEY = "demo-anmeldung"
NAME = "Demo-Anmeldung"
DOMAIN = "demo.example"
CLIENT_ID = "herd-oidc-client"  # the stub's registered client
SECRET_ENV = "HERD_OIDC_STUB_SECRET"  # noqa: S105 -- a variable's name, not a secret


@dataclass
class SeededOidc:
    provider_id: str | None = None


async def stub_provider(admin: httpx.AsyncClient, url: str) -> str:
    """The provider on the stub at `url` (its issuer); fails unless "Prüfen" passes."""
    provider = await call(
        admin,
        "POST",
        "/api/admin/oidc-providers",
        {
            "kind": "generic",
            "key": KEY,
            "name": NAME,
            "issuer": url.rstrip("/"),
            "client_id": CLIENT_ID,
            "client_secret": {"env": SECRET_ENV},
            "allow_signup": True,
            "allowed_domains": [DOMAIN],
            "enabled": True,
        },
    )
    provider_id = str(provider["id"])
    check = await call(admin, "POST", f"/api/admin/oidc-providers/{provider_id}/check")
    if not check["ok"]:
        raise DemoFailed(f"checking {NAME}: {check['code']}")
    return provider_id


async def build(admin: httpx.AsyncClient, *, oidc_stub: str | None) -> SeededOidc:
    seeded = SeededOidc()
    if oidc_stub is not None:
        seeded.provider_id = await stub_provider(admin, oidc_stub)
    return seeded
