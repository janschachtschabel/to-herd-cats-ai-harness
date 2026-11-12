import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


class AuditRepository:
    """Append and read; there is deliberately no way to change or remove an entry."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, entry: AuditLog) -> None:
        self.session.add(entry)
        await self.session.flush()

    async def add_unless_present(self, **values: Any) -> None:
        """Insert unless a unique index already holds such an entry (the daily
        admin-access index); safe under concurrent requests."""
        await self.session.execute(insert(AuditLog).values(**values).on_conflict_do_nothing())

    async def page(
        self,
        org_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
        action: str | None,
        before: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[AuditLog]:
        """Newest first; `before` is the (created_at, id) of the last entry seen."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.org_id == org_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
        )
        if actor_id is not None:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if before is not None:
            stmt = stmt.where(tuple_(AuditLog.created_at, AuditLog.id) < tuple_(*before))
        return list((await self.session.scalars(stmt)).all())
