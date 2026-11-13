"""Helpers for the outbox tests: committed events, recording handlers whose effect is
written in the handler's transaction, and counting those effects.

A handler's visible effect is an `effect.<handler>` event about the original event
(`subject_id` = the event's id), written with `emit` in the handler's own session; it
is committed together with the delivery record, or not at all.
"""

import uuid
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.core.outbox import Event, EventActor, EventDelivery, EventOutbox, emit
from app.core.principal import Principal
from app.worker.registry import HandlerRegistry

Calls = Counter[tuple[uuid.UUID, str]]


async def emit_committed(
    database: Database, org_id: Any, n: int = 1, *, payload: dict[str, Any] | None = None
) -> list[uuid.UUID]:
    """`n` events of type `test.happened`, committed; their ids."""
    actor = EventActor(org_id, Principal.user(uuid.uuid4()))
    ids = []
    async with database.session_factory() as session:
        for i in range(n):
            event = await emit(
                session,
                type="test.happened",
                actor=actor,
                space_id=None,
                subject_type="test",
                subject_id=uuid.uuid4(),
                payload=payload if payload is not None else {"i": i},
            )
            ids.append(event.id)
        await session.commit()
    return ids


async def write_effect(session: AsyncSession, event: Event, handler: str) -> None:
    await emit(
        session,
        type=f"effect.{handler}",
        actor=event.acting,
        space_id=event.space_id,
        subject_type="event",
        subject_id=event.id,
        payload={},
    )


def recording(
    calls: Calls, name: str, *, fail: Callable[[Event], bool] = lambda e: False
) -> Callable[[AsyncSession, Event], Awaitable[None]]:
    """A handler that counts its calls and writes its effect; raises when `fail`."""

    async def _handle(session: AsyncSession, event: Event) -> None:
        calls[(event.id, name)] += 1
        await write_effect(session, event, name)
        if fail(event):
            raise RuntimeError("handler failed")

    return _handle


def registry_of(calls: Calls, names: Iterable[str], **fails: Callable[[Event], bool]) -> Any:
    registry = HandlerRegistry()
    for name in names:
        registry.handler("test", name)(
            recording(calls, name, fail=fails.get(name, lambda e: False))
        )
    return registry


async def effects(database: Database, event_id: uuid.UUID) -> Counter[str]:
    """How often each handler's effect for `event_id` was committed."""
    async with database.session_factory() as session:
        rows = await session.scalars(
            select(EventOutbox.type).where(
                EventOutbox.subject_id == event_id, EventOutbox.type.like("effect.%")
            )
        )
        return Counter(t.removeprefix("effect.") for t in rows)


async def outbox_row(database: Database, event_id: uuid.UUID) -> EventOutbox:
    async with database.session_factory() as session:
        row = await session.get(EventOutbox, event_id)
        assert row is not None
        return row


async def delivered(database: Database, event_id: uuid.UUID) -> set[str]:
    async with database.session_factory() as session:
        rows = await session.scalars(
            select(EventDelivery.handler).where(EventDelivery.event_id == event_id)
        )
        return set(rows)


async def due_now(database: Database) -> None:
    """Bring every waiting retry forward, as if its wait were over."""
    async with database.session_factory() as session:
        await session.execute(update(EventOutbox).values(next_attempt_at=func.now()))
        await session.commit()
