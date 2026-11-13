"""People with open streams for the live-delivery tests (`test_live*.py`): the public
app served by a real uvicorn (`live` fixture), logged-in people, a person of another
organisation, a team channel, and reading what a stream got."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx
import pytest

from app.core.config import get_settings
from app.core.models_base import utcnow
from app.core.principal import SystemRole
from app.core.security import hash_token, new_session_token
from app.modules.auth.models import UserSession
from app.modules.orgs.models import Organization
from app.modules.users.models import User
from app.web.public import create_public_app
from tests.factories import _PASSWORD_HASH, login
from tests.live_helpers import LiveServer, Stream, open_stream
from tests.real_db import RealDb

SECRET = "streng-geheimer-inhalt"


@pytest.fixture
async def live(real_db: RealDb) -> AsyncIterator[LiveServer]:
    server = LiveServer(create_public_app())
    await server.start()
    try:
        yield server
    finally:
        await server.stop()


@dataclass
class Person:
    client: httpx.AsyncClient
    id: str
    org_id: str

    async def stream(self, real_db: RealDb) -> Stream:
        stream = await open_stream(self.client, real_db.database, self.org_id, self.id)
        await stream.settle()
        return stream


async def person(live: LiveServer, email: str) -> Person:
    client = await live.client()
    me = await login(client, email)
    return Person(client, me["user"]["id"], me["org"]["id"])


async def make_person(real_db: RealDb, live: LiveServer, email: str) -> Person:
    async with real_db.database.session_factory() as session:
        session.add(
            User(
                org_id=real_db.org_id,
                email=email,
                name=email.split("@")[0],
                password_hash=_PASSWORD_HASH,
                system_role=SystemRole.MEMBER,
            )
        )
        await session.commit()
    return await person(live, email)


async def stranger(real_db: RealDb, live: LiveServer) -> Person:
    """The owner of another organisation, with a login session of its own (logging in
    looks people up in the installation's one organisation)."""
    token = new_session_token()
    async with real_db.database.session_factory() as session:
        org = Organization(name="Other Org")
        session.add(org)
        await session.flush()
        user = User(
            org_id=org.id,
            email="owner@other.example.com",
            name="Other",
            password_hash=_PASSWORD_HASH,
            system_role=SystemRole.OWNER,
        )
        session.add(user)
        await session.flush()
        session.add(
            UserSession(
                org_id=org.id,
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=utcnow() + timedelta(hours=1),
            )
        )
        await session.commit()
    client = await live.client()
    client.cookies.set(get_settings().session_cookie_name, token)
    return Person(client, str(user.id), str(org.id))


async def team_channel(owner: Person, *members: Person) -> tuple[str, str]:
    """A team space with `members` as viewers, and a channel in it: (space, channel)."""
    space = (await owner.client.post("/api/spaces", json={"name": "Team", "kind": "team"})).json()
    for member in members:
        added = await owner.client.put(
            f"/api/spaces/{space['id']}/members",
            json={"member_type": "user", "member_id": member.id, "role": "viewer"},
        )
        assert added.status_code in (200, 201, 204), added.text
    channel = await owner.client.post(f"/api/spaces/{space['id']}/channels", json={"name": "k"})
    assert channel.status_code == 201, channel.text
    return space["id"], channel.json()["id"]


async def say(who: Person, conversation_id: str, body: str = SECRET) -> dict[str, Any]:
    sent = await who.client.post(
        f"/api/conversations/{conversation_id}/messages", json={"body_md": body}
    )
    assert sent.status_code == 201, sent.text
    message: dict[str, Any] = sent.json()
    return message


@pytest.fixture
async def pair(real_db: RealDb, live: LiveServer) -> tuple[Person, Person]:
    return await person(live, real_db.owner_email), await person(live, real_db.member_email)


async def asyncio_wait(stream: Stream) -> None:
    await asyncio.wait_for(stream.ended.wait(), timeout=10)


def drain_events(stream: Stream) -> list[Any]:
    events = []
    while not stream.events.empty():
        events.append(stream.events.get_nowait())
    return events
