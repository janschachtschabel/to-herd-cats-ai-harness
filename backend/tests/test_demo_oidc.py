"""The demo's sign-in part (scripts/demo_oidc.py, M9): only with a stub's address
(`--oidc-stub`) a generic OIDC provider on it, self-registration open for the demo's
domain; whoever signs up there waits for an admin's approval. Without the address no
provider (never the outside network by default). No secret is kept or printed."""

from collections.abc import Awaitable, Callable
from typing import Any

from httpx import AsyncClient

from app.modules.users.models import User
from scripts import demo_oidc
from scripts.demo_seed import main
from tests.factories import PASSWORD, login
from tests.factories_oidc import error_of, sign_in
from tests.support.oidc_stub import OidcStub
from tests.test_demo_seed import demo  # noqa: F401 -- the fixture


async def _get(client: AsyncClient, path: str) -> Any:
    response = await client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


async def test_without_a_stub_the_demo_has_no_provider(demo: dict[str, Any]) -> None:  # noqa: F811
    seeded = demo["seeded"]
    assert seeded.oidc.provider_id is None
    admin = await demo["connect"]()
    await login(admin, demo["owner"].email, PASSWORD)
    assert (await _get(admin, "/api/admin/oidc-providers?limit=100"))["items"] == []


async def test_with_a_stub_people_of_the_demo_domain_sign_up_and_wait_for_approval(
    make_client: Callable[..., Awaitable[AsyncClient]],
    owner_user: User,
    oidc_egress: OidcStub,
) -> None:
    admin = await make_client(csrf=True)
    await login(admin, owner_user.email, PASSWORD)
    seeded = await demo_oidc.build(admin, oidc_stub=oidc_egress.url)
    provider = await _get(admin, f"/api/admin/oidc-providers/{seeded.provider_id}")
    assert (provider["key"], provider["name"], provider["kind"]) == (
        demo_oidc.KEY,
        demo_oidc.NAME,
        "generic",
    )
    assert provider["issuer"] == oidc_egress.url
    assert (provider["allow_signup"], provider["allowed_domains"], provider["enabled"]) == (
        True,
        [demo_oidc.DOMAIN],
        True,
    )
    assert provider["client_secret"] == {"set": True, "kind": "env"}
    public = await _get(await make_client(), "/api/auth/providers")
    assert [p["key"] for p in public["items"]] == [demo_oidc.KEY]

    browser = await make_client()
    answer = await sign_in(
        browser,
        oidc_egress,
        key=demo_oidc.KEY,
        sub="demo-sub-dora",
        email=f"dora.dorn@{demo_oidc.DOMAIN}",
        name="Dora Dorn",
    )
    assert error_of(answer) == "oidc.account_pending"
    pending = await _get(admin, "/api/admin/users?pending=true&limit=100")
    assert [u["email"] for u in pending["items"]] == [f"dora.dorn@{demo_oidc.DOMAIN}"]

    stranger = await sign_in(
        await make_client(), oidc_egress, key=demo_oidc.KEY, sub="s2", email="eve@elsewhere.example"
    )
    assert error_of(stranger) == "oidc.domain_not_allowed"
    assert "SECRET" not in repr(seeded)


def test_the_seed_takes_an_oidc_stub_address_by_argument(monkeypatch: Any) -> None:
    seen: dict[str, Any] = {}

    async def fake_main(
        base: str, admin_email: str, mcp_stub: str | None, oidc_stub: str | None, *_: Any
    ) -> int:
        seen.update(mcp_stub=mcp_stub, oidc_stub=oidc_stub)
        return 0

    monkeypatch.setattr("scripts.demo_seed._main", fake_main)
    assert main(["--admin", "a@example.com", "--oidc-stub", "https://localhost:8100"]) == 0
    assert seen == {"mcp_stub": None, "oidc_stub": "https://localhost:8100"}
    assert main(["--admin", "a@example.com"]) == 0
    assert seen["oidc_stub"] is None
