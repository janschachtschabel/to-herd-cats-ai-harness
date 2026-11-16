"""The due loop's expiry upkeep (plan M9 task 8): login sessions, OAuth and OIDC flows,
collab grants, rate-limit hits, AI rate windows and sign-ins waiting for a second
factor go once their time column is older than the catalogue's period, across
organisations, in bounded batches; younger rows stay. `remove_expired` is given its time; the due loop gives it the wall time, never
its `SettableClock`."""

import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import Base, utcnow
from app.core.ratelimit import RateLimitHit
from app.core.retention import upkeep_after
from app.models_registry import Base as Registry
from app.modules.agents.run_control_models import RateWindow
from app.modules.ai.models import AiConnection
from app.modules.auth.models import UserSession
from app.modules.connectors.models import AuthKind, Connector, ConnectorScope
from app.modules.oauth.models import OAuthClient, OAuthFlow
from app.modules.oidc.models import OidcFlow, OidcProvider, ProviderKind
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space
from app.modules.spaces.service import SpaceService
from app.modules.totp.models import SignInChallenge
from app.modules.users.models import User
from app.modules.wiki.collab_models import CollabGrant, CollabInstance
from app.modules.wiki.models import Page
from app.worker.due import DueLoop
from app.worker.upkeep import EXPIRING, remove_expired
from tests.real_db import RealDb
from tests.support.clock import SettableClock

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)

Make = Callable[[AsyncSession, Organization, User, datetime], Awaitable[Base]]


def _hex() -> str:
    return secrets.token_hex(32)


async def _login(session: AsyncSession, org: Organization, user: User, at: datetime) -> Base:
    return UserSession(org_id=org.id, user_id=user.id, token_hash=_hex(), expires_at=at)


async def _hit(session: AsyncSession, org: Organization, user: User, at: datetime) -> Base:
    return RateLimitHit(key=f"test:{uuid.uuid4()}", hit_at=at)


async def _window(session: AsyncSession, org: Organization, user: User, at: datetime) -> Base:
    connection = AiConnection(
        org_id=org.id,
        name=f"C {uuid.uuid4()}",
        kind="openai",
        base_url="https://ai.example/v1",
        param_family="max_tokens",
        data_location="eu",
        purpose="chat",
    )
    session.add(connection)
    await session.flush()
    return RateWindow(org_id=org.id, connection_id=connection.id, window_start=at, calls=1)


async def _grant(session: AsyncSession, org: Organization, user: User, at: datetime) -> Base:
    space = await session.scalar(select(Space).where(Space.owner_user_id == user.id))
    if space is None:
        space = await SpaceService(session).create_personal(user)
    slug = f"p-{uuid.uuid4().hex[:8]}"
    page = Page(
        org_id=org.id,
        space_id=space.id,
        title="P",
        slug=slug,
        path=slug,
        created_by_type="user",
        created_by_id=user.id,
        updated_by_type="user",
        updated_by_id=user.id,
    )
    session.add(page)
    await session.flush()
    return CollabGrant(
        org_id=org.id, token_hash=_hex(), page_id=page.id, generation=0, expires_at=at
    )


async def _instance(session: AsyncSession, org: Organization, user: User, at: datetime) -> Base:
    """A collab instance whose last heartbeat was `at` (no organisation: infrastructure)."""
    return CollabInstance(id=uuid.uuid4(), url="ws://collab:1234", heartbeat_at=at)


async def _oauth(session: AsyncSession, org: Organization, user: User, at: datetime) -> Base:
    login = UserSession(org_id=org.id, user_id=user.id, token_hash=_hex(), expires_at=utcnow())
    client = OAuthClient(
        org_id=org.id,
        name=f"App {uuid.uuid4()}",
        authorization_endpoint="https://as.example/authorize",
        token_endpoint="https://as.example/token",
        client_id="c",
        token_auth="client_secret_post",
        scopes="",
    )
    session.add_all([login, client])
    await session.flush()
    connector = Connector(
        org_id=org.id,
        scope=ConnectorScope.SHARED,
        name=f"O {uuid.uuid4()}",
        auth_kind=AuthKind.OAUTH,
        oauth_client_id=client.id,
    )
    session.add(connector)
    await session.flush()
    return OAuthFlow(
        org_id=org.id,
        connector_id=connector.id,
        session_id=login.id,
        state_hash=_hex(),
        verifier_ref="enc:test",
        redirect_uri="https://herd.example/api/ai/oauth/callback",
        expires_at=at,
    )


async def _oidc(session: AsyncSession, org: Organization, user: User, at: datetime) -> Base:
    provider = OidcProvider(
        org_id=org.id,
        key=f"p{uuid.uuid4().hex[:8]}",
        name="P",
        kind=ProviderKind.GENERIC,
        issuer="https://id.example",
        client_id="c",
        scopes="openid email",
    )
    session.add(provider)
    await session.flush()
    return OidcFlow(
        org_id=org.id,
        provider_id=provider.id,
        state_hash=_hex(),
        binding_hash=_hex(),
        nonce=_hex(),
        verifier=_hex(),
        expires_at=at,
    )


async def _challenge(session: AsyncSession, org: Organization, user: User, at: datetime) -> Base:
    return SignInChallenge(
        org_id=org.id, user_id=user.id, token_hash=_hex(), method="password", expires_at=at
    )


MAKERS: dict[str, Make] = {
    "user_session": _login,
    "rate_limit_hit": _hit,
    "ai_rate_window": _window,
    "collab_grant": _grant,
    "collab_instance": _instance,
    "oauth_flow": _oauth,
    "oidc_flow": _oidc,
    "sign_in_challenge": _challenge,
}


def test_every_expiring_table_is_tested_here() -> None:
    assert set(MAKERS) == set(EXPIRING)


async def _ids(session: AsyncSession, table: str) -> set[Any]:
    key = Registry.metadata.tables[table].primary_key.columns.values()[0]
    return set((await session.scalars(select(key))).all())


def _key(row: Base) -> Any:
    return row.__mapper__.primary_key_from_instance(row)[0]


@pytest.mark.parametrize("table", sorted(MAKERS))
async def test_rows_past_their_period_go_and_younger_ones_stay(
    table: str, session: AsyncSession, org: Organization, owner_user: User
) -> None:
    after = upkeep_after(table)
    old, young = [], []
    for at, into in [
        (NOW - after - timedelta(seconds=1), old),
        (NOW - after - timedelta(hours=3), old),
        (NOW - after - timedelta(days=30), old),
        (NOW - after + timedelta(seconds=1), young),
    ]:
        row = await MAKERS[table](session, org, owner_user, at)
        session.add(row)
        await session.flush()
        into.append(_key(row))
    before = await _ids(session, table)
    removed = 0
    while (count := await remove_expired(session, table, NOW, limit=2)) > 0:
        removed += count
    left = await _ids(session, table)
    assert removed >= 3 and not set(old) & left and set(young) <= left
    assert before - left >= set(old)


async def test_the_due_loop_runs_the_upkeep_with_its_cleanup(real_db: RealDb) -> None:
    """By the wall time that wrote and checks the rows, never the loop's clock: a login
    still valid stays while the clock that schedules runs eight days ahead (the browser
    tests' clock, `tests/support/e2e_clock.py`)."""
    now = utcnow()
    async with real_db.database.session_factory() as session:
        owner = await session.scalar(select(User).where(User.email == real_db.owner_email))
        assert owner is not None
        ended = upkeep_after("user_session")
        session.add_all(
            UserSession(org_id=owner.org_id, user_id=owner.id, token_hash=_hex(), expires_at=at)
            for at in [now - ended - timedelta(minutes=1)] * 3 + [now + timedelta(days=7)]
        )
        session.add(RateLimitHit(key="test:old", hit_at=now - timedelta(minutes=5)))
        await session.commit()
    ahead = SettableClock(now + timedelta(days=8))
    loop = DueLoop(real_db.database, clock=ahead, cleanup_batch=2)
    assert await loop.cleanup_if_due() is not None
    async with real_db.database.session_factory() as session:
        sessions = await session.scalar(select(func.count()).select_from(UserSession))
        hits = await session.scalar(select(func.count()).select_from(RateLimitHit))
    assert (sessions, hits) == (1, 0)
