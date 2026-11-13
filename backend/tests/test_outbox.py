"""`outbox.emit`: an event is written in the caller's transaction, and the worker is
woken (`NOTIFY herd_outbox`) only when that transaction commits. Real commits."""

import asyncio
import uuid

import asyncpg
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.outbox import OUTBOX_CHANNEL, EventActor, EventOutbox, emit
from app.core.principal import Principal
from tests.real_db import RealDb


def _actor(real_db: RealDb) -> EventActor:
    return EventActor(real_db.org_id, Principal.user(uuid.uuid4()))


async def _count(real_db: RealDb) -> int:
    async with real_db.database.session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(EventOutbox)) or 0)


async def _listener() -> tuple[asyncpg.Connection, asyncio.Queue[str]]:
    url = get_settings().test_database_url.replace("postgresql+asyncpg", "postgresql")
    connection = await asyncpg.connect(url)
    received: asyncio.Queue[str] = asyncio.Queue()
    await connection.add_listener(OUTBOX_CHANNEL, lambda *args: received.put_nowait(args[3]))
    return connection, received


async def test_emit_is_part_of_the_callers_transaction(real_db: RealDb) -> None:
    connection, received = await _listener()
    try:
        async with real_db.database.session_factory() as session:
            await emit(
                session,
                type="test.created",
                actor=_actor(real_db),
                space_id=None,
                subject_type="test",
                subject_id=uuid.uuid4(),
                payload={"n": 1},
            )
            await session.rollback()
        assert await _count(real_db) == 0
        await asyncio.sleep(0.2)
        assert received.empty()  # nothing to wake the worker for

        subject = uuid.uuid4()
        async with real_db.database.session_factory() as session:
            event = await emit(
                session,
                type="test.created",
                actor=_actor(real_db),
                space_id=None,
                subject_type="test",
                subject_id=subject,
                payload={"n": 2},
            )
            await asyncio.sleep(0.2)
            assert received.empty()  # not before the commit
            await session.commit()
        await asyncio.wait_for(received.get(), timeout=5)
        assert await _count(real_db) == 1
        async with real_db.database.session_factory() as session:
            row = await session.get(EventOutbox, event.id)
        assert row is not None
        assert (row.type, row.subject_id, row.payload) == ("test.created", subject, {"n": 2})
        assert row.org_id == real_db.org_id
        assert (row.attempts, row.dispatched_at, row.failed_at) == (0, None, None)
    finally:
        await connection.close()


async def test_emit_names_the_actor_and_the_space(real_db: RealDb) -> None:
    actor = _actor(real_db)
    async with real_db.database.session_factory() as session:
        event = await emit(
            session,
            type="test.created",
            actor=actor,
            space_id=None,
            subject_type="test",
            subject_id=uuid.uuid4(),
            payload={},
        )
        await session.commit()
    async with real_db.database.session_factory() as session:
        row = await session.get(EventOutbox, event.id)
    assert row is not None
    assert (row.actor_type, row.actor_id, row.space_id) == ("user", actor.principal.id, None)


async def test_a_delivery_record_holds_only_what_is_read(real_db: RealDb) -> None:
    """Hard rule 5 (review M3 N14): the dispatcher reads which handler had which event;
    nothing reads when, so no column holds it."""
    async with real_db.database.session_factory() as session:
        columns = await session.scalars(
            text(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = current_schema() AND table_name = 'event_delivery'"
            )
        )
        assert sorted(columns) == ["event_id", "handler"]
