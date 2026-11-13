"""The dispatcher's SQL on `event_outbox` and `event_delivery`.

Claims lock with `FOR NO KEY UPDATE SKIP LOCKED`: two dispatchers never claim the
same row, and a handler transaction's insert into `event_delivery` (whose foreign key
takes a `KEY SHARE` lock on the event) does not wait for the claim that runs it.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventDelivery, EventOutbox


def _pending() -> tuple[ColumnElement[bool], ...]:
    return (EventOutbox.dispatched_at.is_(None), EventOutbox.failed_at.is_(None))


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(self, limit: int) -> list[EventOutbox]:
        """Due events, oldest first, locked until the transaction ends; events another
        dispatcher holds are skipped."""
        stmt = (
            select(EventOutbox)
            .where(*_pending(), EventOutbox.next_attempt_at <= func.now())
            .order_by(EventOutbox.id)
            .limit(limit)
            .with_for_update(skip_locked=True, key_share=True)
        )
        return list((await self.session.scalars(stmt)).all())

    async def delivered(self, event_ids: Sequence[uuid.UUID]) -> set[tuple[uuid.UUID, str]]:
        """(event, handler) of every delivery recorded for the events."""
        if not event_ids:
            return set()
        stmt = select(EventDelivery.event_id, EventDelivery.handler).where(
            EventDelivery.event_id.in_(event_ids)
        )
        return {(row.event_id, row.handler) for row in await self.session.execute(stmt)}

    async def record_delivery(self, event_id: uuid.UUID, handler: str) -> bool:
        """Record the delivery; False when it is recorded already. A record another
        transaction has written but not committed is waited for."""
        stmt = (
            insert(EventDelivery)
            .values(event_id=event_id, handler=handler)
            .on_conflict_do_nothing(index_elements=["event_id", "handler"])
            .returning(EventDelivery.event_id)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def mark_dispatched(self, event_ids: Sequence[uuid.UUID]) -> None:
        if event_ids:
            stmt = (
                update(EventOutbox)
                .where(EventOutbox.id.in_(event_ids))
                .values(dispatched_at=func.now())
            )
            await self.session.execute(stmt)

    async def retry_later(self, event_id: uuid.UUID, attempts: int, wait: timedelta) -> None:
        stmt = (
            update(EventOutbox)
            .where(EventOutbox.id == event_id)
            .values(attempts=attempts, next_attempt_at=func.now() + wait)
        )
        await self.session.execute(stmt)

    async def mark_failed(self, event_id: uuid.UUID, attempts: int) -> None:
        stmt = (
            update(EventOutbox)
            .where(EventOutbox.id == event_id)
            .values(attempts=attempts, failed_at=func.now())
        )
        await self.session.execute(stmt)

    async def delete_dispatched_before(self, cutoff: datetime, limit: int) -> int:
        """Up to `limit` events dispatched before `cutoff`, with their delivery records
        (cascade); events another dispatcher is deleting are skipped."""
        doomed = (
            select(EventOutbox.id)
            .where(EventOutbox.dispatched_at < cutoff)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        stmt = delete(EventOutbox).where(EventOutbox.id.in_(doomed.scalar_subquery()))
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

    async def limit_time(self, milliseconds: int) -> None:
        """Lock waits and statements of this transaction end after `milliseconds`."""
        value = f"{milliseconds}ms"
        await self.session.execute(
            select(
                func.set_config("lock_timeout", value, True),
                func.set_config("statement_timeout", value, True),
            )
        )
