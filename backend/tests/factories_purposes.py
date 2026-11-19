"""Connectors and OAuth clients of the purpose `calendar` (plan M10 task 13a), made
through the services the calendar routes will call (task 13c): `sync_on` switches the
organisation's calendar sync on, `calendar_client` sets up an OAuth app with
`calendar.manage`, `calendar_connector` connects a person's own access with
`calendar.sync`, `session_id_of` names a person's login session (an OAuth flow is bound
to it)."""

import uuid

from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import UserSession
from app.modules.connectors import purposes
from app.modules.connectors.models import AuthKind, Connector
from app.modules.oauth.clients import ClientService
from app.modules.oauth.models import OAuthClient
from app.modules.oauth.schemas import ClientCreate
from app.modules.users.models import User
from tests.factories_calendar import actor_of
from tests.factories_oauth import client_body
from tests.support.oauth_stub import OAuthStub

SETTINGS = "/api/admin/calendar-settings"
ORIGIN = "https://caldav.example.com"
# Visible ASCII only (`core/secrets.py`); how CalDAV forms Basic is task 15's.
BASIC = "dXNlcjphcHAtcGFzc3dvcmQ="


async def sync_on(admin: AsyncClient, enabled: bool = True) -> None:
    version = (await admin.get(SETTINGS)).json()["version"]
    r = await admin.put(SETTINGS, json={"sync_enabled": enabled, "version": version})
    assert r.status_code == 200, r.text


async def calendar_client(
    session: AsyncSession, admin: User, stub: OAuthStub, name: str = "Google"
) -> OAuthClient:
    body = ClientCreate.model_validate(client_body(stub, name=name, scopes="calendar"))
    actor = await actor_of(session, admin)
    return await ClientService(session, purposes.Purpose.CALENDAR).create(actor, body)


async def calendar_connector(
    session: AsyncSession, user: User, client: OAuthClient | None = None
) -> Connector:
    """A CalDAV access (a header connector) or, given a client, a Google one (OAuth)."""
    actor = await actor_of(session, user)
    if client is not None:
        return await purposes.create_personal(
            session,
            actor,
            purpose=purposes.Purpose.CALENDAR,
            kind=AuthKind.OAUTH,
            origin="https://www.googleapis.com",
            oauth_client_id=client.id,
        )
    return await purposes.create_personal(
        session,
        actor,
        purpose=purposes.Purpose.CALENDAR,
        kind=AuthKind.HEADER,
        origin=ORIGIN,
        header_name="Authorization",
        secret=SecretStr(BASIC),
    )


async def session_id_of(session: AsyncSession, user: User) -> uuid.UUID:
    found = await session.scalar(
        select(UserSession.id).where(UserSession.user_id == user.id).limit(1)
    )
    assert found is not None
    return found
