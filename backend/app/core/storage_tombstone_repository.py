"""Storage tombstones (`core/storage_tombstones.py`): the table and its SQL."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow

MAX_KEY_CHARS = 300


class StorageTombstone(UuidPk, OrgScoped, Base):
    """A file whose rows are gone, waiting for the grace to pass (one per key)."""

    __tablename__ = "storage_tombstone"

    storage_key: Mapped[str] = mapped_column(String(MAX_KEY_CHARS), nullable=False, unique=True)
    buried_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )


class TombstoneRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bury(self, org_id: uuid.UUID, keys: list[str], at: datetime) -> None:
        if not keys:
            return
        stmt = insert(StorageTombstone).values(
            [{"org_id": org_id, "storage_key": key, "buried_at": at} for key in keys]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[StorageTombstone.storage_key],
            set_={"buried_at": stmt.excluded.buried_at},
        )
        await self.session.execute(stmt)

    async def due(self, before: datetime, limit: int) -> list[StorageTombstone]:
        """Oldest first, locked; tombstones another worker holds are passed over."""
        stmt = (
            select(StorageTombstone)
            .where(StorageTombstone.buried_at <= before)
            .order_by(StorageTombstone.buried_at, StorageTombstone.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list((await self.session.scalars(stmt)).all())

    async def remove(self, ids: list[uuid.UUID]) -> None:
        if ids:
            await self.session.execute(
                delete(StorageTombstone)
                .where(StorageTombstone.id.in_(ids))
                .execution_options(synchronize_session=False)
            )
