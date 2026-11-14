"""The dispatcher's SQL on `event_outbox`, `event_lane` and `event_delivery`.

- Routing takes new events `FOR NO KEY UPDATE SKIP LOCKED`, so two workers route
  disjoint events, and writes their lanes in the same transaction that marks them
  routed: once an event is seen routed, all its lanes are there.
- A lane's batch takes its rows `FOR UPDATE SKIP LOCKED`: two workers never hold the
  same (event, handler). A delivery record's foreign key takes only a `KEY SHARE`
  lock on the event, which no claim or finish conflicts with.
- Finishing locks the batch's events `FOR NO KEY UPDATE` in the order of their ids
  (no deadlock between lanes) and then reads what is left of their lanes: the lane
  that finishes an event last sees every other lane's commit, so no event is left
  pending with nothing left to do.
"""

import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import (
    BindParameter,
    ColumnElement,
    String,
    bindparam,
    delete,
    func,
    literal,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import MAX_HANDLER_CHARS, EventDelivery, EventLane, EventOutbox
from app.core.repository import limit_time, locked_batch


def _pending() -> tuple[ColumnElement[bool], ...]:
    return (EventOutbox.dispatched_at.is_(None), EventOutbox.failed_at.is_(None))


# Rows go in as one array per column (`unnest`): one parameter each, however many rows.
def _uuids(values: Sequence[uuid.UUID]) -> BindParameter[Any]:
    return bindparam(None, list(values), type_=cast(Any, ARRAY(PG_UUID(as_uuid=True))))


def _texts(values: Sequence[str]) -> BindParameter[Any]:
    return bindparam(None, list(values), type_=cast(Any, ARRAY(String(MAX_HANDLER_CHARS))))


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- routing ------------------------------------------------------------------

    async def unrouted(self, limit: int) -> list[tuple[uuid.UUID, str]]:
        """(id, type) of events not routed yet, oldest first, locked until the
        transaction ends; events another worker routes are skipped."""
        stmt = (
            select(EventOutbox.id, EventOutbox.type)
            .where(EventOutbox.routed_at.is_(None), *_pending())
            .order_by(EventOutbox.id)
            .limit(limit)
            .with_for_update(skip_locked=True, key_share=True)
        )
        return [(row.id, row.type) for row in await self.session.execute(stmt)]

    async def delivered(self, event_ids: Sequence[uuid.UUID]) -> set[tuple[uuid.UUID, str]]:
        """(event, handler) of every delivery recorded for the events (by a worker of
        the previous release, which knows no lanes)."""
        if not event_ids:
            return set()
        stmt = select(EventDelivery.event_id, EventDelivery.handler).where(
            EventDelivery.event_id.in_(event_ids)
        )
        return {(row.event_id, row.handler) for row in await self.session.execute(stmt)}

    async def add_lanes(self, lanes: Sequence[tuple[uuid.UUID, str]]) -> None:
        if lanes:
            rows = (
                func.unnest(
                    _uuids([event_id for event_id, _ in lanes]), _texts([name for _, name in lanes])
                )
                .table_valued("event_id", "handler")
                .render_derived()
            )
            stmt = (
                pg_insert(EventLane)
                .from_select(["event_id", "handler"], select(rows.c.event_id, rows.c.handler))
                .on_conflict_do_nothing()
            )
            await self.session.execute(stmt)

    async def mark_routed(self, event_ids: Sequence[uuid.UUID], done: Iterable[uuid.UUID]) -> None:
        """Routed; `done` (events no handler wants) dispatched as well."""
        if event_ids:
            await self.session.execute(
                update(EventOutbox)
                .where(EventOutbox.id.in_(event_ids))
                .values(routed_at=func.now())
            )
        await self.mark_dispatched(list(done))

    # --- a lane's batch -----------------------------------------------------------

    async def claim(self, handler: str, limit: int) -> list[tuple[EventOutbox, int]]:
        """The handler's due events with its attempts so far, oldest first; its lane
        rows stay locked until the transaction ends, rows another worker holds are
        skipped."""
        stmt = (
            select(EventOutbox, EventLane.attempts)
            .join(EventLane, EventLane.event_id == EventOutbox.id)
            .where(
                EventLane.handler == handler,
                EventLane.failed_at.is_(None),
                EventLane.next_attempt_at <= func.now(),
            )
            .order_by(EventLane.event_id)
            .limit(limit)
            .with_for_update(of=EventLane, skip_locked=True)
        )
        return [(row[0], int(row[1])) for row in await self.session.execute(stmt)]

    async def record_deliveries(
        self, event_ids: Sequence[uuid.UUID], handler: str
    ) -> set[uuid.UUID]:
        """Record the handler's delivery of the events; the ids whose record is new (the
        others were delivered already). A record another transaction has written but
        not committed is waited for."""
        if not event_ids:
            return set()
        ids = func.unnest(_uuids(event_ids)).table_valued("event_id").render_derived()
        stmt = (
            pg_insert(EventDelivery)
            .from_select(
                ["event_id", "handler"],
                select(ids.c.event_id, literal(handler, String(MAX_HANDLER_CHARS))),
            )
            .on_conflict_do_nothing(index_elements=["event_id", "handler"])
            .returning(EventDelivery.event_id)
        )
        return set((await self.session.scalars(stmt)).all())

    async def unrecord_deliveries(self, event_ids: Sequence[uuid.UUID], handler: str) -> None:
        """Take back the records of deliveries whose handler failed or did not run."""
        if event_ids:
            await self.session.execute(
                delete(EventDelivery).where(
                    EventDelivery.handler == handler, EventDelivery.event_id.in_(event_ids)
                )
            )

    async def drop_lanes(self, event_ids: Sequence[uuid.UUID], handler: str) -> None:
        """The handler has had these events."""
        if event_ids:
            await self.session.execute(
                delete(EventLane).where(
                    EventLane.handler == handler, EventLane.event_id.in_(event_ids)
                )
            )

    async def retry_later(
        self, event_id: uuid.UUID, handler: str, attempts: int, wait: timedelta
    ) -> None:
        await self.session.execute(
            update(EventLane)
            .where(EventLane.event_id == event_id, EventLane.handler == handler)
            .values(attempts=attempts, next_attempt_at=func.now() + wait)
        )

    async def give_up(self, event_id: uuid.UUID, handler: str, attempts: int) -> None:
        await self.session.execute(
            update(EventLane)
            .where(EventLane.event_id == event_id, EventLane.handler == handler)
            .values(attempts=attempts, failed_at=func.now())
        )

    async def finish(
        self, event_ids: Sequence[uuid.UUID]
    ) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
        """Mark the pending events among these whose lanes are all done: dispatched when
        none is left, failed when only lanes that gave up are left. (dispatched, failed)."""
        if not event_ids:
            return [], []
        locked = list(
            await self.session.scalars(
                select(EventOutbox.id)
                .where(EventOutbox.id.in_(event_ids), *_pending())
                .order_by(EventOutbox.id)
                .with_for_update(key_share=True)
            )
        )
        if not locked:
            return [], []
        stmt = (
            select(EventLane.event_id, func.bool_and(EventLane.failed_at.is_not(None)))
            .where(EventLane.event_id.in_(locked))
            .group_by(EventLane.event_id)
        )
        left = {row[0]: bool(row[1]) for row in await self.session.execute(stmt)}
        dispatched = [event_id for event_id in locked if event_id not in left]
        failed = [event_id for event_id, all_failed in left.items() if all_failed]
        await self.mark_dispatched(dispatched)
        if failed:
            await self.session.execute(
                update(EventOutbox).where(EventOutbox.id.in_(failed)).values(failed_at=func.now())
            )
        return dispatched, failed

    async def mark_dispatched(self, event_ids: Sequence[uuid.UUID]) -> None:
        if event_ids:
            stmt = (
                update(EventOutbox)
                .where(EventOutbox.id.in_(event_ids))
                .values(dispatched_at=func.now())
            )
            await self.session.execute(stmt)

    async def limit_time(self, milliseconds: int) -> None:
        """Lock waits and statements of this transaction end after `milliseconds`."""
        await limit_time(self.session, milliseconds, milliseconds)

    # --- upkeep and gauges --------------------------------------------------------

    async def delete_dispatched_before(self, cutoff: datetime, limit: int) -> int:
        """Up to `limit` events dispatched before `cutoff`, with their delivery records
        (cascade); events another dispatcher is deleting are skipped."""
        doomed = locked_batch(
            select(EventOutbox.id)
            .where(EventOutbox.dispatched_at < cutoff)
            .limit(limit)
            .with_for_update(skip_locked=True),
            "doomed",
        )
        stmt = delete(EventOutbox).where(EventOutbox.id == doomed.c.id)
        result = await self.session.execute(stmt)
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def backlog(self) -> tuple[int, datetime | None]:
        """How many events are pending, and when the oldest was written."""
        stmt = select(func.count(), func.min(EventOutbox.created_at)).where(*_pending())
        count, oldest = (await self.session.execute(stmt)).one()
        return int(count), oldest

    async def failed_count(self) -> int:
        """How many events gave up and are still in the table."""
        stmt = select(func.count()).where(EventOutbox.failed_at.is_not(None))
        return int(await self.session.scalar(stmt) or 0)
