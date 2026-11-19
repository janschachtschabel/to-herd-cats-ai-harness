import uuid
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import PrincipalType
from app.modules.audit.models import AuditLog
from app.modules.users.models import User


class NamedEntry(NamedTuple):
    """An entry with its actor's display name (None if the actor is not a person)."""

    entry: AuditLog
    actor_name: str | None


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

    async def add_many_unless_present(self, rows: list[dict[str, Any]]) -> None:
        """`add_unless_present` for several entries, in one statement."""
        if rows:
            await self.session.execute(insert(AuditLog).values(rows).on_conflict_do_nothing())

    async def page(
        self,
        org_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
        action: str | None,
        before: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[NamedEntry]:
        """Newest first; `before` is the (created_at, id) of the last entry seen."""
        name = (
            select(User.name)
            .where(AuditLog.actor_type == PrincipalType.USER, User.id == AuditLog.actor_id)
            .scalar_subquery()
        )
        stmt = (
            select(AuditLog, name)
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
        return [NamedEntry(e, n) for e, n in (await self.session.execute(stmt)).all()]

    async def latest_of(self, org_id: uuid.UUID, actions: tuple[str, ...]) -> AuditLog | None:
        """The newest entry with one of `actions` (the last restore attempt, plan M9
        task 13)."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.org_id == org_id, AuditLog.action.in_(actions))
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)
