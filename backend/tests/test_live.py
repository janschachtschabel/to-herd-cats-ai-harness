"""Live delivery (plan M3 task 7, review focus 1): `GET /api/stream` over the worker's
`publish_live` handler and each API process's LISTEN hub, against a real server and
real commits. Payloads carry ids only; who gets an event is decided per event, from
the database as it is then."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import update

from app.core.config import get_settings
from app.core.models_base import utcnow
from app.core.principal import SystemRole
from app.core.security import hash_token, new_session_token
from app.modules.auth.models import UserSession
from app.modules.orgs.models import Organization
from app.modules.users.models import User
from app.web.public import create_public_app
from tests.factories import _PASSWORD_HASH, login
from tests.live_helpers import LiveServer, Stream, drain, open_stream, until
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


async def test_member_receives_message_event_with_ids_only(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    _, channel = await team_channel(owner, member)
    await drain(real_db.database)
    stream = await member.stream(real_db)
    response = stream.response
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"

    message = await say(owner, channel)
    await drain(real_db.database)
    event = await stream.next()
    assert event.name == "message.created"
    assert event.data == {
        "conversation_id": channel,
        "message_id": message["id"],
        "parent_id": None,
    }
    reply = await owner.client.post(
        f"/api/conversations/{channel}/messages",
        json={"body_md": SECRET, "parent_id": message["id"]},
    )
    await drain(real_db.database)
    event = await stream.next()
    assert event.data["parent_id"] == message["id"]
    assert event.data["message_id"] == reply.json()["id"]
    await stream.expect_nothing()
    assert not any(SECRET in line for line in stream.raw)
    await stream.close()


async def test_non_member_and_other_org_receive_nothing(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    _, channel = await team_channel(owner)  # the member is not in it
    other = await stranger(real_db, live)
    await drain(real_db.database)
    streams = [await member.stream(real_db), await other.stream(real_db)]
    await say(owner, channel)
    await drain(real_db.database)
    for stream in streams:
        await stream.expect_nothing()
        await stream.close()


async def test_revoked_member_stops_receiving_without_reconnect(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    space, channel = await team_channel(owner, member)
    await drain(real_db.database)
    stream = await member.stream(real_db)
    await say(owner, channel, "vorher")
    await drain(real_db.database)
    assert (await stream.next()).name == "message.created"

    removed = await owner.client.delete(f"/api/spaces/{space}/members/user/{member.id}")
    assert removed.status_code == 204, removed.text
    await say(owner, channel)
    await drain(real_db.database)
    await stream.expect_nothing()
    assert not stream.ended.is_set()  # the same connection, still open
    await stream.close()


async def test_dm_event_reaches_only_participants_not_admins(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    carol = await make_person(real_db, live, "carol@real.example.com")
    dm = (await member.client.post("/api/dms", json={"user_ids": [carol.id]})).json()
    inspection = await owner.client.post(
        "/api/admin/dm-inspect",
        json={"conversation_id": dm["id"], "reason": "a reason that is long enough"},
    )
    assert inspection.status_code == 201, inspection.text  # an inspection opens no stream
    await drain(real_db.database)
    watching = [
        await owner.stream(real_db),
        await member.stream(real_db),
        await carol.stream(real_db),
    ]
    message = await say(member, dm["id"])
    await drain(real_db.database)
    for stream in watching[1:]:
        event = await stream.until_event("message.created")
        assert event.data["message_id"] == message["id"]
    await watching[0].expect_nothing()
    for stream in watching:
        await stream.close()


async def test_events_for_one_person_reach_only_that_person(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    """`notification.created` and `conversation.read` name their person (`u`)."""
    owner, member = pair
    viewer = await make_person(real_db, live, "viewer@real.example.com")
    _, channel = await team_channel(owner, member, viewer)
    await drain(real_db.database)
    streams = [await member.stream(real_db), await viewer.stream(real_db)]
    sent = await owner.client.post(
        f"/api/conversations/{channel}/messages",
        json={"body_md": "@member", "mentions": [member.id]},
    )
    await drain(real_db.database)
    message_id = sent.json()["id"]
    notified = await streams[0].until_event("notification.created")
    assert notified.data == {
        "conversation_id": channel,
        "message_id": message_id,
        "parent_id": None,
    }
    read = await member.client.post(
        f"/api/conversations/{channel}/read", json={"message_id": message_id}
    )
    assert read.status_code == 204
    await drain(real_db.database)
    assert (await streams[0].until_event("conversation.read")).data["message_id"] == message_id
    await streams[0].expect_nothing()
    assert (await streams[1].next()).name == "message.created"  # the viewer: only the message
    await streams[1].expect_nothing()
    for stream in streams:
        await stream.close()


async def test_stream_closes_after_logout(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    _, channel = await team_channel(owner, member)
    await drain(real_db.database)
    watcher, leaving = await owner.stream(real_db), await member.stream(real_db)
    assert (await member.client.post("/api/auth/logout")).status_code == 204
    await say(owner, channel)
    await drain(real_db.database)
    await watcher.until_event("message.created")  # the hub has handled the event
    await watcher.expect_nothing()
    await live.hub.check_sessions()  # what the hub does every 30 s
    await asyncio_wait(leaving)
    assert [e.name for e in drain_events(leaving)] == []  # nothing after the logout
    await watcher.close()
    await leaving.close()


async def test_the_session_check_runs_on_its_own(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.messaging import live as live_module

    monkeypatch.setattr(live_module, "SESSION_CHECK_SECONDS", 0.2)
    _, member = pair
    stream = await member.stream(real_db)
    async with real_db.database.session_factory() as session:  # deactivated, session kept
        await session.execute(update(User).where(User.id == member.id).values(is_active=False))
        await session.commit()
    await asyncio_wait(stream)
    await stream.close()


async def test_sixth_connection_is_429(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    _, member = pair
    streams = [
        await open_stream(member.client, real_db.database, member.org_id, member.id)
        for _ in range(5)
    ]
    sixth = await member.client.get("/api/stream")
    assert sixth.status_code == 429
    assert sixth.json()["error"]["code"] == "live.too_many_streams"
    other_session = await person(live, real_db.member_email)  # another login: its own five
    extra = await open_stream(other_session.client, real_db.database, member.org_id, member.id)
    await streams[0].close()
    await until(lambda: live.hub.stream_count() == 5)
    again = await open_stream(member.client, real_db.database, member.org_id, member.id)
    for stream in [*streams[1:], extra, again]:
        await stream.close()


async def test_heartbeat_and_retry_hint(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.messaging import live_connection as live_module

    monkeypatch.setattr(live_module, "HEARTBEAT_SECONDS", 0.1)
    _, member = pair
    stream = await open_stream(member.client, real_db.database, member.org_id, member.id)
    await until(lambda: len(stream.comments) >= 2)
    assert stream.retry == [str(live_module.RETRY_MS)]
    await stream.close()


async def test_lost_listen_connection_sends_resync(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    _, member = pair
    stream = await member.stream(real_db)
    async with real_db.database.engine.connect() as connection:
        from sqlalchemy import text

        terminated = await connection.scalar(
            text(
                "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity"
                " WHERE datname = current_database() AND query = 'LISTEN \"herd_live\"'"
            )
        )
    assert terminated == 1
    assert (await stream.next()).name == "resync"
    await until(lambda: live.hub.listening)
    await stream.settle()  # delivers again
    await stream.close()


async def asyncio_wait(stream: Stream) -> None:
    import asyncio

    await asyncio.wait_for(stream.ended.wait(), timeout=10)


def drain_events(stream: Stream) -> list[Any]:
    events = []
    while not stream.events.empty():
        events.append(stream.events.get_nowait())
    return events
