"""The SQL of collab instances and page bindings (`collab_instances.py`, plan M9
decision 17).

`collab_instance` is infrastructure without an organisation: announcing, releasing
and choosing an instance are not scoped (the internal API is trusted). Bindings
(`collab_page_owner`) are scoped by the page's organisation; releasing an instance
leaves its bindings of every organisation without owner (`ON DELETE SET NULL`).

Locks: a claim takes the binding's row lock (its upsert); a save locks the binding
after the page row, so a page cannot change hands between a save's owner check and
its commit, and the new owner loads the page only after that save."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, and_, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wiki.collab_models import CollabInstance, CollabPageOwner


@dataclass(frozen=True, slots=True)
class Binding:
    """A page's owner as stored: its instance (None: gone), epoch and expiry."""

    instance_id: uuid.UUID | None
    epoch: int
    expires_at: datetime


def _live(alive_since: datetime) -> ColumnElement[bool]:
    """The instance of a binding still beats and is not released. Not as a correlated
    EXISTS: in an upsert's conflict clause that would read `collab_page_owner` anew in
    the statement's snapshot instead of the row it conflicts with. False, never NULL,
    for a binding without instance (its NOT must hold)."""
    beating = select(CollabInstance.id).where(CollabInstance.heartbeat_at > alive_since)
    owner = CollabPageOwner.instance_id
    return and_(owner.is_not(None), owner.in_(beating))


async def database_now(session: AsyncSession) -> datetime:
    """The database server's clock: one for every API node (review M9b F11)."""
    now: datetime | None = await session.scalar(select(func.clock_timestamp()))
    assert now is not None  # clock_timestamp() is never NULL
    return now


class CollabInstanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def announce(
        self, instance_id: uuid.UUID, url: str, *, draining: bool, now: datetime
    ) -> None:
        """Insert or beat; once draining, an instance stays draining."""
        stmt = insert(CollabInstance).values(
            id=instance_id, url=url, heartbeat_at=now, draining=draining
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[CollabInstance.id],
            set_={
                "url": stmt.excluded.url,
                "heartbeat_at": stmt.excluded.heartbeat_at,
                "draining": CollabInstance.draining | stmt.excluded.draining,
            },
        )
        await self.session.execute(stmt)

    async def release(self, instance_id: uuid.UUID) -> None:
        """The instance is gone: its bindings lose their owner (`ON DELETE SET NULL`)."""
        await self.session.execute(delete(CollabInstance).where(CollabInstance.id == instance_id))

    async def url(self, instance_id: uuid.UUID) -> str | None:
        return await self.session.scalar(
            select(CollabInstance.url).where(CollabInstance.id == instance_id)
        )

    async def least_busy(self, *, alive_since: datetime, now: datetime) -> uuid.UUID | None:
        """The live, not draining instance with the fewest pages bound to it right now
        (ties: the lowest id)."""
        pages = func.count(CollabPageOwner.page_id)
        stmt = (
            select(CollabInstance.id)
            .outerjoin(
                CollabPageOwner,
                and_(
                    CollabPageOwner.instance_id == CollabInstance.id,
                    CollabPageOwner.expires_at > now,
                ),
            )
            .where(CollabInstance.heartbeat_at > alive_since, CollabInstance.draining.is_(False))
            .group_by(CollabInstance.id)
            .order_by(pages, CollabInstance.id)
            .limit(1)
        )
        return await self.session.scalar(stmt)


class CollabOwnerRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def binding(self, page_id: uuid.UUID, *, lock: bool = False) -> Binding | None:
        stmt = select(
            CollabPageOwner.instance_id, CollabPageOwner.epoch, CollabPageOwner.expires_at
        ).where(CollabPageOwner.org_id == self.org_id, CollabPageOwner.page_id == page_id)
        if lock:
            stmt = stmt.with_for_update()
        row = (await self.session.execute(stmt)).one_or_none()
        return Binding(row.instance_id, row.epoch, row.expires_at) if row else None

    async def valid(
        self, page_id: uuid.UUID, *, now: datetime, alive_since: datetime
    ) -> Binding | None:
        """The binding if it holds: not expired, its instance alive."""
        stmt = select(
            CollabPageOwner.instance_id, CollabPageOwner.epoch, CollabPageOwner.expires_at
        ).where(
            CollabPageOwner.org_id == self.org_id,
            CollabPageOwner.page_id == page_id,
            CollabPageOwner.expires_at > now,
            _live(alive_since),
        )
        row = (await self.session.execute(stmt)).one_or_none()
        return Binding(row.instance_id, row.epoch, row.expires_at) if row else None

    async def claim(
        self,
        page_id: uuid.UUID,
        instance_id: uuid.UUID,
        *,
        now: datetime,
        alive_since: datetime,
        until: datetime,
    ) -> int | None:
        """Bind the page to the instance with the next epoch, unless a binding holds
        (then None: someone else won the race). Atomic in the binding's row lock."""
        new = insert(CollabPageOwner).values(
            page_id=page_id, org_id=self.org_id, instance_id=instance_id, epoch=1, expires_at=until
        )
        holds = and_(CollabPageOwner.expires_at > now, _live(alive_since))
        stmt = new.on_conflict_do_update(
            index_elements=[CollabPageOwner.page_id],
            set_={
                "instance_id": new.excluded.instance_id,
                "epoch": CollabPageOwner.epoch + 1,
                "expires_at": new.excluded.expires_at,
            },
            where=and_(CollabPageOwner.org_id == self.org_id, ~holds),
        ).returning(CollabPageOwner.epoch)
        epoch: int | None = await self.session.scalar(stmt)
        return epoch

    async def extend(
        self, page_id: uuid.UUID, instance_id: uuid.UUID, epoch: int, *, until: datetime
    ) -> None:
        """Push the binding's expiry, if it is still this instance's with this epoch."""
        await self.session.execute(
            update(CollabPageOwner)
            .where(
                CollabPageOwner.org_id == self.org_id,
                CollabPageOwner.page_id == page_id,
                CollabPageOwner.instance_id == instance_id,
                CollabPageOwner.epoch == epoch,
            )
            .values(expires_at=until)
        )
