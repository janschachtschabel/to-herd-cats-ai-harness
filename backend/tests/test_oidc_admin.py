"""OIDC administration and linked accounts (plan M9 task 4)."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.oidc.models import OidcProvider
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories import PASSWORD, login
from tests.factories_oidc import PROVIDERS, error_of, make_provider, sign_in
from tests.support.oidc_stub import OidcStub

pytestmark = pytest.mark.usefixtures("oidc_egress")
REAUTH = {"password": PASSWORD}  # linking asks for the password again (J9)


async def test_provider_admin_needs_user_manage_and_version(
    owner: AsyncClient,
    member_client: AsyncClient,
    oidc_stub: OidcStub,
    secret_key: None,
    session: AsyncSession,
) -> None:
    created = await make_provider(owner, oidc_stub, client_secret={"value": "very-secret-value-1"})
    for method, path in (
        ("GET", PROVIDERS),
        ("GET", f"{PROVIDERS}/{created['id']}"),
        ("PATCH", f"{PROVIDERS}/{created['id']}"),
        ("POST", f"{PROVIDERS}/{created['id']}/check"),
    ):
        json = {"version": 1, "name": "x"} if method == "PATCH" else None
        refused = await member_client.request(method, path, json=json)
        assert refused.status_code == 403, (method, path)
        assert refused.json()["error"]["code"] == "auth.permission_denied"
    assert created["client_secret"] == {"set": True, "kind": "enc"}
    patched = await owner.patch(
        f"{PROVIDERS}/{created['id']}", json={"version": created["version"], "name": "Neu"}
    )
    assert patched.status_code == 200 and patched.json()["name"] == "Neu"
    stale = await owner.patch(
        f"{PROVIDERS}/{created['id']}", json={"version": created["version"], "name": "Alt"}
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "oidc.version_conflict"
    listed = await owner.get(PROVIDERS)
    every_answer = created, patched.json(), listed.json()
    assert "very-secret-value-1" not in str(every_answer)
    row = await session.scalar(select(OidcProvider).where(OidcProvider.id == created["id"]))
    assert row is not None and row.client_secret_ref is not None
    assert row.client_secret_ref.startswith("enc:")
    audits = (
        await session.scalars(select(AuditLog).where(AuditLog.target_type == "oidc_provider"))
    ).all()
    assert [a.action for a in audits] == ["oidc_provider.created", "oidc_provider.updated"]
    assert "very-secret" not in str([a.details for a in audits])
    deleted = await owner.delete(
        f"{PROVIDERS}/{created['id']}", params={"version": patched.json()["version"]}
    )
    assert deleted.status_code == 204


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"kind": "google", "client_id": "c", "issuer": "https://x.test"}, "oidc.preset_fixed"),
        ({"kind": "google", "client_id": "c"}, "oidc.secret_required"),
        ({"kind": "generic", "client_id": "c", "key": "k", "name": "K"}, "oidc.fields_required"),
        (
            {
                "kind": "generic",
                "client_id": "c",
                "key": "k",
                "name": "K",
                "issuer": "http://x.test",
            },
            "oidc.url_not_allowed",
        ),
        (
            {
                "kind": "generic",
                "client_id": "c",
                "key": "k",
                "name": "K",
                "issuer": "https://x.test",
                "scopes": "email",
            },
            "oidc.scopes_invalid",
        ),
        (
            {
                "kind": "generic",
                "client_id": "c",
                "key": "k",
                "name": "K",
                "issuer": "https://x.test",
                "allow_signup": True,
            },
            "oidc.domains_required",
        ),
        (
            {
                "kind": "generic",
                "client_id": "c",
                "key": "k",
                "name": "K",
                "issuer": "https://x.test",
                "allowed_domains": ["example.com."],
            },
            "oidc.domain_invalid",
        ),
        (
            {
                "kind": "generic",
                "client_id": "c",
                "key": "k",
                "name": "K",
                "issuer": "https://x.test",
                "allowed_domains": ["*.example.com"],
            },
            "oidc.domain_invalid",
        ),
        (
            {
                "kind": "generic",
                "client_id": "c",
                "key": "k",
                "name": "K",
                "issuer": "https://x.test",
                "client_secret": {"env": "HERD_AI_KEY"},
            },
            "secrets.env_name_invalid",
        ),
        (
            {
                "kind": "generic",
                "client_id": "c",
                "key": "k",
                "name": "K",
                "issuer": "https://x.test",
                "client_secret": {"env": "HERD_OIDC_ALLOWED_HOSTS"},
            },
            "secrets.env_name_invalid",
        ),
    ],
)
async def test_provider_writes_are_checked(
    owner: AsyncClient, body: dict[str, Any], code: str
) -> None:
    response = await owner.post(PROVIDERS, json=body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == code


async def test_switching_on_needs_the_public_url(
    owner: AsyncClient, oidc_stub: OidcStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings  # noqa: PLC0415

    monkeypatch.setattr(get_settings(), "public_url", None)
    body = {"kind": "generic", "client_id": "c", "key": "k", "name": "K", "issuer": oidc_stub.url}
    off = await owner.post(PROVIDERS, json=body)
    assert off.status_code == 201 and off.json()["callback_url"] is None
    on = await owner.patch(f"{PROVIDERS}/{off.json()['id']}", json={"version": 1, "enabled": True})
    assert on.status_code == 422 and on.json()["error"]["code"] == "oidc.public_url_missing"


async def test_domains_are_kept_lower_case_and_the_key_is_unique(
    owner: AsyncClient, oidc_stub: OidcStub
) -> None:
    created = await make_provider(owner, oidc_stub, allowed_domains=["Example.COM", "example.com"])
    assert created["allowed_domains"] == ["example.com"]
    assert created["callback_url"] == "https://herd.example/api/auth/oidc/stub/callback"
    again = await owner.post(
        PROVIDERS,
        json={
            "kind": "generic",
            "client_id": "c",
            "key": "stub",
            "name": "S",
            "issuer": oidc_stub.url,
        },
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "oidc.key_taken"


async def test_public_providers_list_shows_only_enabled_ones(
    owner: AsyncClient, client: AsyncClient, oidc_stub: OidcStub
) -> None:
    await make_provider(owner, oidc_stub)
    await make_provider(owner, oidc_stub, key="off", name="Off", enabled=False)
    listed = await client.get("/api/auth/providers")
    assert listed.status_code == 200
    assert listed.json()["items"] == [{"key": "stub", "name": "Stub IdP", "kind": "generic"}]


async def test_link_from_the_profile_and_unlink(
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    oidc_stub: OidcStub,
    make_client: MakeClient,
    session: AsyncSession,
) -> None:
    """The profile links an account whatever its email; another person's account is
    refused; the last way into a password-less account stays."""
    await make_provider(owner, oidc_stub)
    started = await member_client.post("/api/auth/me/identities/stub/link", json=REAUTH)
    assert started.status_code == 200, started.text
    oidc_stub.state.identity.update(sub="max-at-idp", email="max.private@else.test")
    query = oidc_stub.state.authorize(started.json()["url"])
    done = await member_client.get("/api/auth/oidc/stub/callback", params=query)
    assert done.headers["location"] == "/profile?linked=stub"
    mine = (await member_client.get("/api/auth/me/identities")).json()["items"]
    assert [(i["provider_key"], i["provider_name"]) for i in mine] == [("stub", "Stub IdP")]
    browser = await make_client()
    assert (await sign_in(browser, oidc_stub, sub="max-at-idp")).headers["location"] == "/"
    # Owner links the same account: taken.
    started = await owner.post("/api/auth/me/identities/stub/link", json=REAUTH)
    query = oidc_stub.state.authorize(started.json()["url"])
    done = await owner.get("/api/auth/oidc/stub/callback", params=query)
    assert error_of(done) == "oidc.identity_taken"
    assert done.headers["location"].startswith("/profile?link_error=")
    # The admin view, then unlink; without a password the last one stays.
    admin_view = await owner.get(f"/api/admin/users/{member.id}/identities")
    assert [i["id"] for i in admin_view.json()["items"]] == [mine[0]["id"]]
    own = await member_client.get(f"/api/admin/users/{member.id}/identities")
    assert own.status_code == 403  # the administration's path needs user.manage, own or not
    member.password_hash = None
    await session.flush()
    last = await member_client.delete(f"/api/auth/me/identities/{mine[0]['id']}")
    assert last.status_code == 409 and last.json()["error"]["code"] == "oidc.last_identity"


async def test_others_identities_need_user_manage_and_unlink_is_audited(
    owner: AsyncClient,
    member_client: AsyncClient,
    owner_user: User,
    member: User,
    oidc_stub: OidcStub,
    session: AsyncSession,
) -> None:
    await make_provider(owner, oidc_stub, trust_email=True)
    started = await owner.post("/api/auth/me/identities/stub/link", json=REAUTH)
    query = oidc_stub.state.authorize(started.json()["url"])
    await owner.get("/api/auth/oidc/stub/callback", params=query)
    refused = await member_client.get(f"/api/admin/users/{owner_user.id}/identities")
    assert refused.status_code == 403
    items = (await owner.get("/api/auth/me/identities")).json()["items"]
    removed = await owner.delete(f"/api/admin/users/{owner_user.id}/identities/{items[0]['id']}")
    assert removed.status_code == 204
    audit = await session.scalar(
        select(AuditLog).where(AuditLog.action == "user.identity_unlinked")
    )
    assert audit is not None and audit.details == {"provider": "stub"}
    unknown = await owner.delete(f"/api/auth/me/identities/{items[0]['id']}")
    assert unknown.status_code == 404


async def test_deleting_a_provider_removes_its_links(
    owner: AsyncClient, member_client: AsyncClient, member: User, oidc_stub: OidcStub
) -> None:
    created = await make_provider(owner, oidc_stub)
    started = await member_client.post("/api/auth/me/identities/stub/link", json=REAUTH)
    await member_client.get(
        "/api/auth/oidc/stub/callback", params=oidc_stub.state.authorize(started.json()["url"])
    )
    assert len((await member_client.get("/api/auth/me/identities")).json()["items"]) == 1
    gone = await owner.delete(f"{PROVIDERS}/{created['id']}", params={"version": 1})
    assert gone.status_code == 204
    await login(member_client, member.email)  # her sessions ended with it (N5)
    assert (await member_client.get("/api/auth/me/identities")).json()["items"] == []


async def test_unlinking_an_identity_ends_the_persons_other_sessions(
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_client: MakeClient,
    oidc_stub: OidcStub,
) -> None:
    """ASVS 5.0 V7.4.3: removing a way to sign in ends every other session of the
    person (a session someone opened with it included); one's own change keeps the
    session it is made with, an administrator's ends them all."""
    await make_provider(owner, oidc_stub, trust_email=True)
    other = await make_client()
    done = await sign_in(other, oidc_stub, email=member.email, sub="s-two")
    assert done.headers["location"] == "/"
    mine = (await member_client.get("/api/auth/me/identities")).json()["items"]
    assert (
        await member_client.delete(f"/api/auth/me/identities/{mine[0]['id']}")
    ).status_code == 204
    assert (await other.get("/api/auth/me")).status_code == 401
    assert (await member_client.get("/api/auth/me")).status_code == 200

    await sign_in(other, oidc_stub, email=member.email, sub="s-three")
    linked = (await member_client.get("/api/auth/me/identities")).json()["items"]
    path = f"/api/admin/users/{member.id}/identities/{linked[0]['id']}"
    assert (await owner.delete(path)).status_code == 204
    assert (await other.get("/api/auth/me")).status_code == 401
    assert (await member_client.get("/api/auth/me")).status_code == 401
    assert (await owner.get("/api/auth/me")).status_code == 200
