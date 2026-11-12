import hashlib
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.models_base import utcnow
from app.core.principal import Principal, PrincipalType, SystemRole
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.modules.auth.models import UserSession
from app.modules.orgs.models import Organization
from app.modules.orgs.service import ensure_bootstrap
from app.modules.users.models import User
from tests.conftest import json_lines
from tests.factories import CSRF, PASSWORD, login

bad_creds = {"email": "nobody@example.com", "password": "wrong-password"}


async def test_me_requires_login(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.required"


async def test_login_sets_cookie_and_me_works(client: AsyncClient, owner_user: User) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": "Owner@Example.com", "password": PASSWORD}, headers=CSRF
    )
    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith("herd_session=")
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    body = response.json()
    assert body["user"]["email"] == "owner@example.com"
    assert body["user"]["system_role"] == "owner"
    assert body["user"]["version"] == owner_user.version
    assert body["org"] == {"id": str(owner_user.org_id), "name": "Test Org", "slug": "test-org"}
    assert "password_hash" not in body["user"]

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["id"] == body["user"]["id"]
    assert me.json()["user"]["last_login_at"] is not None


async def test_login_wrong_password(client: AsyncClient, owner_user: User) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": owner_user.email, "password": "nope"}, headers=CSRF
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.invalid_credentials"


async def test_login_unknown_email_without_any_org(client: AsyncClient) -> None:
    response = await client.post("/api/auth/login", json=bad_creds, headers=CSRF)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.invalid_credentials"


async def test_inactive_user_cannot_login(client: AsyncClient, make_user) -> None:
    user = await make_user(is_active=False)
    response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": PASSWORD}, headers=CSRF
    )
    assert response.status_code == 401


async def test_login_is_rate_limited(client: AsyncClient) -> None:
    for _ in range(5):
        await client.post("/api/auth/login", json=bad_creds, headers=CSRF)
    response = await client.post("/api/auth/login", json=bad_creds, headers=CSRF)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "auth.too_many_attempts"


async def test_logout_invalidates_session(owner: AsyncClient, session: AsyncSession) -> None:
    response = await owner.post("/api/auth/logout")
    assert response.status_code == 204
    assert 'herd_session=""' in response.headers["set-cookie"]
    assert (await owner.get("/api/auth/me")).status_code == 401
    assert await session.scalar(select(func.count()).select_from(UserSession)) == 0


async def test_csrf_header_required_for_unsafe_methods(client: AsyncClient, owner_user) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": owner_user.email, "password": PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "auth.csrf"


async def test_session_token_is_stored_hashed_with_client_details(
    client: AsyncClient, owner_user: User, session: AsyncSession
) -> None:
    await client.post(
        "/api/auth/login",
        json={"email": owner_user.email, "password": PASSWORD},
        headers={**CSRF, "User-Agent": "pytest-browser"},
    )
    token = client.cookies["herd_session"]
    stored = (await session.scalars(select(UserSession))).one()
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest() != token
    assert stored.user_agent == "pytest-browser"
    assert stored.ip == "127.0.0.1"
    assert stored.org_id == owner_user.org_id
    assert timedelta(hours=167) < stored.expires_at - utcnow() <= timedelta(hours=168)


async def test_expired_session_is_rejected(owner: AsyncClient, session: AsyncSession) -> None:
    await session.execute(update(UserSession).values(expires_at=utcnow() - timedelta(seconds=1)))
    response = await owner.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.session_invalid"


async def test_unknown_token_is_rejected(client: AsyncClient) -> None:
    client.cookies.set("herd_session", new_session_token())
    response = await client.get("/api/auth/me")
    assert response.json()["error"]["code"] == "auth.session_invalid"


async def test_password_is_never_logged(client: AsyncClient, owner_user: User, capsys) -> None:
    capsys.readouterr()
    await login(client, owner_user.email)
    await client.post(
        "/api/auth/login", json={"email": owner_user.email, "password": "secret-typo"}, headers=CSRF
    )
    out = capsys.readouterr().out
    assert PASSWORD not in out and "secret-typo" not in out
    assert client.cookies["herd_session"] not in out


async def test_resolved_user_is_bound_to_log_lines(owner: AsyncClient, owner_user, capsys) -> None:
    capsys.readouterr()
    assert (await owner.get("/api/_test/whoami")).status_code == 200
    line = next(x for x in json_lines(capsys.readouterr().out) if x["message"] == "test.whoami")
    assert line["org_id"] == str(owner_user.org_id)
    assert line["actor"] == f"user:{owner_user.id}"


def test_principal() -> None:
    id_ = uuid.uuid4()
    assert Principal.user(id_) == Principal(PrincipalType.USER, id_)
    assert Principal.group(id_).type is PrincipalType.GROUP
    assert str(Principal.user(id_)) == f"user:{id_}"
    assert [t.value for t in PrincipalType] == ["user", "agent", "group"]
    assert [r.value for r in SystemRole] == ["owner", "admin", "member", "guest"]


def test_password_and_token_primitives() -> None:
    hashed = hash_password("correct horse")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "correct horse")
    assert not verify_password(hashed, "wrong horse")
    assert not verify_password("not-a-hash", "correct horse")
    token = new_session_token()
    assert len(token) >= 43 and hash_token(token) == hashlib.sha256(token.encode()).hexdigest()


# --- bootstrap -----------------------------------------------------------------------

BOOT = Settings(
    bootstrap_admin_email="Boss@Example.com",
    bootstrap_admin_password="boss-password-123",
    bootstrap_org_name="Müller & Söhne",
)


async def test_bootstrap_creates_org_and_owner(session: AsyncSession, client: AsyncClient) -> None:
    await ensure_bootstrap(session, BOOT)
    org = (await session.scalars(select(Organization))).one()
    assert (org.name, org.slug) == ("Müller & Söhne", "mueller-soehne")
    user = (await session.scalars(select(User))).one()
    assert (user.email, user.system_role, user.org_id) == ("boss@example.com", "owner", org.id)
    await login(client, "boss@example.com", "boss-password-123")


async def test_bootstrap_is_idempotent(session: AsyncSession) -> None:
    await ensure_bootstrap(session, BOOT)
    await ensure_bootstrap(session, BOOT.model_copy(update={"bootstrap_admin_email": "x@y.de"}))
    assert await session.scalar(select(func.count()).select_from(User)) == 1
    assert await session.scalar(select(func.count()).select_from(Organization)) == 1


async def test_bootstrap_does_nothing_once_someone_exists(session, owner_user) -> None:
    await ensure_bootstrap(session, BOOT)
    assert await session.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.parametrize("missing", ["bootstrap_admin_email", "bootstrap_admin_password"])
async def test_bootstrap_without_credentials_creates_nothing(session, missing, capsys) -> None:
    await ensure_bootstrap(session, BOOT.model_copy(update={missing: ""}))
    assert await session.scalar(select(func.count()).select_from(Organization)) == 0
    assert "bootstrap.skipped" in capsys.readouterr().out


async def test_bootstrap_takes_a_lock(session: AsyncSession) -> None:
    """Two replicas starting at once must not both create an organisation."""
    await ensure_bootstrap(session, BOOT)
    held = await session.scalar(
        text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()")
    )
    assert held == 1
