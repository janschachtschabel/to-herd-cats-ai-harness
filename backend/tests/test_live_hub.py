"""The live hub's parts on their own: the slow client's queue, one query per event for
every connected person, no pool connection held by open streams, and the handler's
NOTIFY payload."""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import Database, set_database
from app.core.listen import asyncpg_dsn
from app.modules.auth.models import UserSession
from app.modules.messaging import live as live_module
from app.modules.messaging.live import Connection, LiveHub
from app.modules.messaging.live_events import LIVE_CHANNEL, LiveEvent, decode
from app.modules.users.models import User
from app.web.public import create_public_app
from tests.factories import login
from tests.live_helpers import LiveServer, drain, open_stream
from tests.real_db import MakeRealClient, RealDb


def test_slow_client_gets_resync_instead_of_growing_queue() -> None:
    connection = Connection(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    event = LiveEvent("message.created", uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), None, None)
    for _ in range(live_module.QUEUE_SIZE):
        connection.push(event.frame())
    assert connection.queue.qsize() == live_module.QUEUE_SIZE
    connection.push(event.frame())  # one too many: the client has fallen behind
    assert connection.queue.qsize() == 1
    assert connection.queue.get_nowait() == live_module.RESYNC
    connection.push(event.frame())
    assert connection.queue.get_nowait() == event.frame()


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "x",
        "[]",
        json.dumps({"t": "message.created"}),
        json.dumps(
            {"t": "nope", "o": str(uuid.uuid4()), "c": None, "m": None, "p": None, "u": None}
        ),
        json.dumps({"t": "message.created", "o": "x", "c": None, "m": None, "p": None, "u": None}),
        json.dumps(
            {
                "t": "message.created",
                "o": str(uuid.uuid4()),
                "c": 5,
                "m": None,
                "p": None,
                "u": None,
            }
        ),
    ],
)
def test_a_payload_the_hub_cannot_use_is_dropped(raw: str) -> None:
    assert decode(raw) is None


async def _sessions(real_db: RealDb, emails: list[str]) -> list[tuple[uuid.UUID, uuid.UUID]]:
    async with real_db.database.session_factory() as session:
        rows = await session.execute(
            select(UserSession.id, User.id)
            .join(User, User.id == UserSession.user_id)
            .where(User.email.in_(emails))
        )
        return [(row[0], row[1]) for row in rows]


async def test_one_query_per_event_for_all_connected_people(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, member = await make_real_client(), await make_real_client()
    await login(owner, real_db.owner_email)
    await login(member, real_db.member_email)
    await login(await make_real_client(), real_db.member_email)  # a second session
    space = (await owner.post("/api/spaces", json={"name": "T", "kind": "open"})).json()
    channel = (await owner.post(f"/api/spaces/{space['id']}/channels", json={"name": "k"})).json()
    hub = LiveHub()
    hub.database = real_db.database
    connections = [
        hub.connect(real_db.org_id, user_id, session_id)  # type: ignore[arg-type]
        for session_id, user_id in await _sessions(
            real_db, [real_db.owner_email, real_db.member_email]
        )
        for _ in range(2)
    ]
    assert len(connections) == 6
    statements: list[str] = []

    def count(*args: object) -> None:
        statements.append(str(args[2]))

    engine = real_db.database.engine.sync_engine
    sa_event.listen(engine, "before_cursor_execute", count)
    try:
        for _ in range(3):
            await hub.deliver(
                LiveEvent(
                    "message.created",
                    real_db.org_id,  # type: ignore[arg-type]
                    uuid.UUID(channel["id"]),
                    uuid.uuid4(),
                    None,
                    None,
                )
            )
    finally:
        sa_event.remove(engine, "before_cursor_execute", count)
    assert len(statements) == 3, statements  # one per event, not one per connection
    assert all(c.queue.qsize() == 3 for c in connections)  # an open space: everyone


@pytest.fixture
async def one_connection(real_db: RealDb) -> AsyncIterator[Database]:
    database = Database(
        get_settings().test_database_url, pool_size=1, max_overflow=0, pool_timeout=10
    )
    set_database(database)
    try:
        yield database
    finally:
        set_database(real_db.database)
        await database.dispose()


async def test_stream_holds_no_pool_connection(real_db: RealDb, one_connection: Database) -> None:
    """With a pool of one connection, open streams leave it to other requests."""
    server = LiveServer(create_public_app())
    await server.start()
    try:
        client = await server.client(real_db.member_email)
        me = (await client.get("/api/auth/me")).json()["user"]
        streams = [
            await open_stream(client, real_db.database, real_db.org_id, me["id"]) for _ in range(3)
        ]
        started = time.perf_counter()
        assert (await client.get("/api/auth/me")).status_code == 200
        assert time.perf_counter() - started < 1.0
        space = (await client.post("/api/spaces", json={"name": "T", "kind": "open"})).json()
        channel = await client.post(f"/api/spaces/{space['id']}/channels", json={"name": "k"})
        assert channel.status_code == 201
        await drain(real_db.database)
        for stream in streams:
            assert (await stream.until_event("channel.changed")).data["conversation_id"] == (
                channel.json()["id"]
            )
        assert one_connection.engine.pool.checkedout() == 0  # type: ignore[attr-defined]
        for stream in streams:
            await stream.close()
        await client.aclose()
    finally:
        await server.stop()


async def test_publish_live_notifies_ids_only(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space = (await owner.post("/api/spaces", json={"name": "T", "kind": "team"})).json()
    channel = (await owner.post(f"/api/spaces/{space['id']}/channels", json={"name": "k"})).json()
    await drain(real_db.database)
    received: list[str] = []
    arrived = asyncio.Event()

    def on_notify(*args: object) -> None:
        received.append(str(args[3]))
        arrived.set()

    listener = await asyncpg.connect(asyncpg_dsn(real_db.database.engine.url))
    await listener.add_listener(LIVE_CHANNEL, on_notify)
    try:
        sent = await owner.post(
            f"/api/conversations/{channel['id']}/messages", json={"body_md": "geheim"}
        )
        await drain(real_db.database)
        await asyncio.wait_for(arrived.wait(), timeout=5)
    finally:
        await listener.close()
    payload = json.loads(received[0])
    assert payload == {
        "t": "message.created",
        "o": str(real_db.org_id),
        "c": channel["id"],
        "m": sent.json()["id"],
        "p": None,
        "u": None,
    }
    assert len(received[0].encode()) < 4000
