"""The live hub in batches (review M3 N1): whatever has arrived is handled together,
with at most two statements for the whole batch, and a hub that has fallen further
behind than its limit drops what waits and sends `resync` instead of delivering ever
later."""

import asyncio
import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event as sa_event
from sqlalchemy import select

from app.core.metrics import REGISTRY
from app.modules.auth.models import UserSession
from app.modules.messaging.live import LiveHub
from app.modules.messaging.live_connection import RESYNC, Connection
from app.modules.users.models import User
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb


async def _sessions(real_db: RealDb, email: str) -> list[tuple[uuid.UUID, uuid.UUID]]:
    async with real_db.database.session_factory() as session:
        rows = await session.execute(
            select(UserSession.id, User.id)
            .join(User, User.id == UserSession.user_id)
            .where(User.email == email)
        )
        return [(row[0], row[1]) for row in rows]


@contextmanager
def statements(real_db: RealDb) -> Iterator[list[str]]:
    seen: list[str] = []

    def count(*args: object) -> None:
        seen.append(str(args[2]))

    engine = real_db.database.engine.sync_engine
    sa_event.listen(engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        sa_event.remove(engine, "before_cursor_execute", count)


def _payload(name: str, org: object, conversation: object = None, user: object = None) -> str:
    return json.dumps(
        {
            "t": name,
            "o": str(org),
            "c": None if conversation is None else str(conversation),
            "m": str(uuid.uuid4()),
            "p": None,
            "u": None if user is None else str(user),
        }
    )


def _frames(connection: Connection) -> list[bytes]:
    frames = []
    while not connection.queue.empty():
        frame = connection.queue.get_nowait()
        assert frame is not None
        frames.append(frame)
    return frames


def _names(connection: Connection) -> list[str]:
    return [f.decode().split("\n")[0].removeprefix("event: ") for f in _frames(connection)]


async def test_a_batch_is_answered_with_two_statements_whatever_its_size(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, member = await make_real_client(), await make_real_client()
    await login(owner, real_db.owner_email)
    await login(member, real_db.member_email)
    open_space = (await owner.post("/api/spaces", json={"name": "O", "kind": "open"})).json()
    team = (await owner.post("/api/spaces", json={"name": "T", "kind": "team"})).json()
    channels = [
        (await owner.post(f"/api/spaces/{s['id']}/channels", json={"name": "k"})).json()["id"]
        for s in (open_space, team)
    ]
    hub = LiveHub()
    hub.database = real_db.database
    [(owner_session, owner_id)] = await _sessions(real_db, real_db.owner_email)
    [(member_session, member_id)] = await _sessions(real_db, real_db.member_email)
    owner_stream = hub.connect(real_db.org_id, owner_id, owner_session)  # type: ignore[arg-type]
    member_stream = hub.connect(real_db.org_id, member_id, member_session)  # type: ignore[arg-type]
    org = real_db.org_id
    batch = []
    for i in range(60):  # the open channel, the team channel, a person's own event
        batch.append(_payload("message.created", org, channels[i % 2]))
        batch.append(_payload("activity.changed", org, user=member_id))
    batch.append(_payload("message.created", uuid.uuid4(), channels[0]))  # another org
    now = time.monotonic()
    with statements(real_db) as seen:
        await hub.handle([(raw, now) for raw in batch])
    assert len(seen) == 2, seen
    owner_names = _names(owner_stream)
    member_names = _names(member_stream)
    assert owner_names == ["message.created"] * 60  # both channels, no one else's event
    assert member_names.count("message.created") == 30  # only the open channel
    assert member_names.count("activity.changed") == 60
    assert member_names[:2] == ["message.created", "activity.changed"]  # in arrival order

    with statements(real_db) as seen:  # only people's own events: one statement
        await hub.handle([(_payload("activity.changed", org, user=owner_id), now)])
    assert len(seen) == 1
    assert _names(owner_stream) == ["activity.changed"]


async def test_a_hub_further_behind_than_its_limit_drops_the_queue_and_resyncs(
    real_db: RealDb,
) -> None:
    hub = LiveHub(max_lag_seconds=0.05)
    hub.database = real_db.database
    stream = hub.connect(real_db.org_id, uuid.uuid4(), uuid.uuid4())  # type: ignore[arg-type]
    for _ in range(5):
        hub._received(_payload("message.created", real_db.org_id, uuid.uuid4()))
    assert _gauge("herd_live_queue_depth") == 5
    await asyncio.sleep(0.1)  # the oldest waits longer than the limit
    lag_before = _counter("herd_live_resyncs_total", reason="lag")
    with statements(real_db) as seen:
        await hub.handle([hub._incoming.get_nowait()])
    assert seen == []  # nothing was checked or delivered
    assert _frames(stream) == [RESYNC]
    assert hub._incoming.empty()
    assert _gauge("herd_live_queue_depth") == 0
    assert _counter("herd_live_resyncs_total", reason="lag") == lag_before + 1

    hub._received(_payload("message.created", real_db.org_id, uuid.uuid4()))  # fresh: no resync
    await hub.handle([hub._incoming.get_nowait()])
    assert _frames(stream) == []  # (nobody may see an unknown conversation)


async def test_the_lag_of_delivered_events_is_measured(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    hub = LiveHub()
    hub.database = real_db.database
    [(session_id, user_id)] = await _sessions(real_db, real_db.owner_email)
    stream = hub.connect(real_db.org_id, user_id, session_id)  # type: ignore[arg-type]
    count_before = _counter("herd_live_delivery_lag_seconds_count")
    slow_before = _counter("herd_live_delivery_lag_seconds_bucket", le="1.0")
    raw = _payload("activity.changed", real_db.org_id, user=user_id)
    await hub.handle([(raw, time.monotonic() - 2.0)])  # arrived two seconds ago
    assert _names(stream) == ["activity.changed"]
    assert _counter("herd_live_delivery_lag_seconds_count") == count_before + 1
    assert _counter("herd_live_delivery_lag_seconds_bucket", le="1.0") == slow_before


def _gauge(name: str) -> float:
    value = REGISTRY.get_sample_value(name)
    assert value is not None
    return value


def _counter(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_the_lag_limit_comes_from_the_settings() -> None:
    from app.core.config import Settings  # noqa: PLC0415
    from app.web.public import create_public_app  # noqa: PLC0415

    app = create_public_app(Settings(live_max_lag_seconds=2.5))
    assert app.state.live.max_lag_seconds == 2.5
    assert create_public_app(Settings()).state.live.max_lag_seconds == 5.0
