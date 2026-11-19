import hashlib
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import Settings
from app.core.models_base import utcnow
from app.core.principal import Principal, PrincipalType, SystemRole
from app.core.security import (
    dummy_password_hash,
    hash_password,
    hash_token,
    needs_rehash,
    new_session_token,
    verify_password,
)
from app.modules.auth import service as auth_service
from app.modules.auth.models import UserSession
from app.modules.auth.repository import SessionRepository
from app.modules.orgs.models import Organization
from app.modules.orgs.service import ensure_bootstrap
from app.modules.users.models import User
from tests.conftest import json_lines
from tests.factories import CSRF, PASSWORD, login
from tests.support.plans import force_nested_loops

bad_creds = {"email": "nobody@example.com", "password": "wrong-password"}


async def test_me_requires_login(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.required"


async def test_cookie_is_secure_when_the_request_came_over_https(
    client: AsyncClient, owner_user: User
) -> None:
    """Behind a trusted reverse proxy uvicorn takes the scheme from X-Forwarded-Proto;
    the session cookie is then Secure without HERD_COOKIE_SECURE."""
    body = {"email": owner_user.email, "password": PASSWORD}
    plain = await client.post("/api/auth/login", json=body, headers=CSRF)
    assert "secure" not in plain.headers["set-cookie"].lower()
    https = await client.post("https://test/api/auth/login", json=body, headers=CSRF)
    assert https.status_code == 200
    assert "secure" in https.headers["set-cookie"].lower()


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
    assert body["org"] == {"id": str(owner_user.org_id), "name": "Test Org"}
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
    # The row stays, ended, until a login clears it (live editing still needs to know
    # whose session it was: review M2 R2).
    ended = select(func.count()).select_from(UserSession).where(UserSession.expires_at <= utcnow())
    assert await session.scalar(ended) == 1
    assert await session.scalar(select(func.count()).select_from(UserSession)) == 1


async def test_csrf_header_required_for_unsafe_methods(client: AsyncClient, owner_user) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": owner_user.email, "password": PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "auth.csrf"


async def test_session_token_is_stored_hashed(
    client: AsyncClient, owner_user: User, session: AsyncSession
) -> None:
    await login(client, owner_user.email)
    token = client.cookies["herd_session"]
    stored = (await session.scalars(select(UserSession))).one()
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest() != token
    assert stored.org_id == owner_user.org_id
    assert timedelta(hours=167) < stored.expires_at - utcnow() <= timedelta(hours=168)


async def test_sessions_store_no_client_details(session: AsyncSession) -> None:
    """Nothing reads a session's address, so it is not kept; of the browser only a
    device hint without version (J8), and its last use for the idle limit (J7)."""
    columns = await session.run_sync(
        lambda s: {c["name"] for c in inspect(s.connection()).get_columns("user_session")}
    )
    assert columns == {
        *("id", "org_id", "user_id", "token_hash", "expires_at"),
        *("last_used_at", "signed_in_at", "device", "reauth_at"),
    }


@pytest.mark.parametrize("case", ["unknown", "inactive", "no_password"])
async def test_login_without_a_usable_account_still_verifies_a_hash(
    client: AsyncClient, make_user, monkeypatch, case: str
) -> None:
    """Timing must not tell whether an account exists: a dummy hash is verified."""
    calls: list[str] = []
    monkeypatch.setattr(security, "verify_password", lambda h, p: calls.append(h) or False)
    email = "nobody@example.com"
    if case == "inactive":
        email = (await make_user(is_active=False)).email
    elif case == "no_password":
        user = await make_user()
        user.password_hash = None
        email = user.email
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}, headers=CSRF
    )
    assert response.status_code == 401
    assert calls == [dummy_password_hash()]


async def _expired_session(session: AsyncSession, user: User) -> None:
    session.add(
        UserSession(
            org_id=user.org_id,
            user_id=user.id,
            token_hash=hash_token(new_session_token()),
            expires_at=utcnow() - timedelta(hours=2),  # longer than ENDED_SESSION_KEEP
        )
    )
    await session.flush()


async def test_login_deletes_expired_sessions_of_anyone(
    owner: AsyncClient, owner_user: User, member: User, session: AsyncSession, make_client
) -> None:
    for user in (owner_user, member):
        await _expired_session(session, user)
    await login(await make_client(csrf=True), owner_user.email)
    rows = (await session.execute(select(UserSession.user_id, UserSession.expires_at))).all()
    # Both expired ones are gone (also the other person's, who may never log in again);
    # the owner's two live ones (fixture, new login) stay.
    assert sorted((uid == owner_user.id, exp > utcnow()) for uid, exp in rows) == [
        (True, True),
        (True, True),
    ]


async def test_expired_sessions_are_deleted_in_bounded_batches(
    owner_user: User, member: User, session: AsyncSession, make_client, monkeypatch
) -> None:
    monkeypatch.setattr(auth_service, "EXPIRED_SESSION_BATCH", 2)
    for _ in range(3):
        await _expired_session(session, member)
    await login(await make_client(csrf=True), owner_user.email)
    expired = select(func.count()).select_from(UserSession).where(UserSession.expires_at < utcnow())
    assert await session.scalar(expired) == 1


async def test_one_batch_deletes_at_most_its_limit_whatever_the_plan(
    member: User, session: AsyncSession
) -> None:
    """With `IN (subquery … LIMIT n FOR UPDATE SKIP LOCKED)` a nested-loop semi-join
    runs the subquery again per outer row and deletes more than n; the batch must hold
    whatever plan the planner picks (here forced to a nested loop)."""
    for _ in range(5):
        await _expired_session(session, member)
    await force_nested_loops(session)
    await SessionRepository(session).delete_expired(member.org_id, utcnow(), 2)
    expired = select(func.count()).select_from(UserSession).where(UserSession.expires_at < utcnow())
    assert await session.scalar(expired) == 3


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
    lines = json_lines(capsys.readouterr().out)
    for message in ("test.whoami", "http.request"):
        line = next(x for x in lines if x["message"] == message)
        assert line["org_id"] == str(owner_user.org_id)
        assert line["actor"] == f"user:{owner_user.id}"


async def test_anonymous_request_line_names_nobody(client: AsyncClient, capsys) -> None:
    capsys.readouterr()
    await client.get("/api/auth/me")
    line = next(x for x in json_lines(capsys.readouterr().out) if x["message"] == "http.request")
    assert "actor" not in line and "org_id" not in line


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
    bootstrap_admin_password=SecretStr("lantern-orbit-73-q"),
    bootstrap_org_name="Müller & Söhne",
)


async def test_bootstrap_creates_org_and_owner(session: AsyncSession, client: AsyncClient) -> None:
    await ensure_bootstrap(session, BOOT)
    org = (await session.scalars(select(Organization))).one()
    assert org.name == "Müller & Söhne"
    user = (await session.scalars(select(User))).one()
    assert (user.email, user.system_role, user.org_id) == ("boss@example.com", "owner", org.id)
    await login(client, "boss@example.com", "lantern-orbit-73-q")


async def test_bootstrap_is_idempotent(session: AsyncSession) -> None:
    await ensure_bootstrap(session, BOOT)
    await ensure_bootstrap(session, BOOT.model_copy(update={"bootstrap_admin_email": "x@y.de"}))
    assert await session.scalar(select(func.count()).select_from(User)) == 1
    assert await session.scalar(select(func.count()).select_from(Organization)) == 1


async def test_bootstrap_does_nothing_once_someone_exists(session, owner_user) -> None:
    await ensure_bootstrap(session, BOOT)
    assert await session.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.parametrize(
    ("missing", "empty"),
    [("bootstrap_admin_email", ""), ("bootstrap_admin_password", SecretStr(""))],
)
async def test_bootstrap_without_credentials_creates_nothing(
    session, missing, empty, capsys
) -> None:
    await ensure_bootstrap(session, BOOT.model_copy(update={missing: empty}))
    assert await session.scalar(select(func.count()).select_from(Organization)) == 0
    assert "bootstrap.skipped" in capsys.readouterr().out


async def test_bootstrap_takes_a_lock(session: AsyncSession) -> None:
    """Two replicas starting at once must not both create an organisation."""
    await ensure_bootstrap(session, BOOT)
    held = await session.scalar(
        text(
            "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory'"
            " AND pid = pg_backend_pid()"
            " AND ((classid::bigint << 32) | objid::bigint) = hashtextextended('bootstrap', 0)"
        )
    )
    assert held == 1


async def test_a_login_rehashes_a_password_stored_with_old_parameters(
    client: AsyncClient, owner_user: User, session: AsyncSession
) -> None:
    """ASVS 5.0 V11.2.2: when the hashing parameters move on, each person's hash moves
    with them at their next login (the old one still verifies until then)."""
    from argon2 import PasswordHasher  # noqa: PLC0415

    weak = PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1).hash(PASSWORD)
    owner_user.password_hash = weak
    await session.flush()
    body = {"email": owner_user.email, "password": PASSWORD}
    assert (await client.post("/api/auth/login", json=body, headers=CSRF)).status_code == 200
    await session.refresh(owner_user)
    assert owner_user.password_hash != weak
    assert not needs_rehash(owner_user.password_hash)
    assert verify_password(owner_user.password_hash, PASSWORD)
