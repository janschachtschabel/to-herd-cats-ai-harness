"""The SQL of AI assignments (spec 7.2): the organisation's standard, the ordered
group assignments, a person's own; and the one statement that resolves which applies
to a person (`effective`). Every statement is scoped by the organisation."""

import uuid
from dataclasses import dataclass

from sqlalchemy import and_, delete, exists, false, func, literal, or_, select, true, union_all
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import PrincipalType
from app.core.repository import advisory_xact_lock
from app.modules.agents.models import Agent
from app.modules.ai.models import AiConnection, GroupAssignment, OrgAssignment, UserAssignment
from app.modules.groups.models import Group, GroupMember
from app.modules.users.models import User

SOURCES = {1: "user", 2: "group", 3: "default"}


@dataclass(frozen=True, slots=True)
class Resolved:
    """What applies to a person, before the rules (`effective.py`) judge it. `source`
    is None when nothing applies; the connection fields are None without one."""

    system_role: str
    is_active: bool
    source: str | None
    no_ai: bool
    connection_id: uuid.UUID | None
    model: str | None
    connection_enabled: bool | None
    connection_purpose: str | None
    model_listed: bool | None


@dataclass(frozen=True, slots=True)
class Named[T]:
    row: T
    name: str
    connection_name: str | None


class AssignmentRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def org(self) -> tuple[OrgAssignment | None, str | None]:
        """The standard assignment's row (None before the first write) and the name of
        its connection."""
        stmt = (
            select(OrgAssignment, AiConnection.name)
            .outerjoin(AiConnection, AiConnection.id == OrgAssignment.connection_id)
            .where(OrgAssignment.org_id == self.org_id)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        return (row[0], row[1]) if row else (None, None)

    async def lock_org(self) -> OrgAssignment:
        """The row, created at version 1 if missing, locked until the transaction ends."""
        await self.session.execute(
            insert(OrgAssignment)
            .values(org_id=self.org_id, version=1)
            .on_conflict_do_nothing(index_elements=["org_id"])
        )
        stmt = (
            select(OrgAssignment)
            .where(OrgAssignment.org_id == self.org_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).one()

    async def group_page(self, after: int | None, limit: int) -> list[Named[GroupAssignment]]:
        stmt = (
            select(GroupAssignment, Group.name, AiConnection.name)
            .join(Group, Group.id == GroupAssignment.group_id)
            .join(AiConnection, AiConnection.id == GroupAssignment.connection_id)
            .where(GroupAssignment.org_id == self.org_id)
            .order_by(GroupAssignment.position)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(GroupAssignment.position > after)
        rows = (await self.session.execute(stmt)).all()
        return [Named(row[0], row[1], row[2]) for row in rows]

    async def replace_groups(self, items: list[GroupAssignment]) -> None:
        await self.session.execute(
            delete(GroupAssignment).where(GroupAssignment.org_id == self.org_id)
        )
        await self.session.flush()
        self.session.add_all(items)
        await self.session.flush()

    async def user_page(self, after: uuid.UUID | None, limit: int) -> list[Named[UserAssignment]]:
        stmt = (
            select(UserAssignment, User.name, AiConnection.name)
            .join(User, User.id == UserAssignment.user_id)
            .outerjoin(AiConnection, AiConnection.id == UserAssignment.connection_id)
            .where(UserAssignment.org_id == self.org_id)
            .order_by(UserAssignment.user_id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(UserAssignment.user_id > after)
        rows = (await self.session.execute(stmt)).all()
        return [Named(row[0], row[1], row[2]) for row in rows]

    async def lock_user(self, user_id: uuid.UUID) -> None:
        """Serialise writes of one person's assignment, the first one included."""
        await advisory_xact_lock(self.session, f"ai.user_assignment:{self.org_id}:{user_id}")

    async def user(self, user_id: uuid.UUID) -> UserAssignment | None:
        stmt = (
            select(UserAssignment)
            .where(UserAssignment.org_id == self.org_id, UserAssignment.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def add(self, row: UserAssignment) -> UserAssignment:
        self.session.add(row)
        await self.session.flush()
        return row

    async def delete(self, row: UserAssignment) -> None:
        await self.session.delete(row)
        await self.session.flush()

    async def connection_in_use(self, connection_id: uuid.UUID) -> bool:
        """Whether an assignment or an agent (M5 task 5) uses the connection."""
        uses = [
            exists().where(table.org_id == self.org_id, table.connection_id == connection_id)
            for table in (OrgAssignment, GroupAssignment, UserAssignment, Agent)
        ]
        return bool(await self.session.scalar(select(or_(*uses))))

    async def group_ids(self) -> list[uuid.UUID]:
        """The groups that have an assignment now."""
        stmt = select(GroupAssignment.group_id).where(GroupAssignment.org_id == self.org_id)
        return list(await self.session.scalars(stmt))

    async def resolve(self, user_id: uuid.UUID) -> Resolved | None:
        """Person before group (lowest position first) before the standard, and the
        state of the chosen connection, in one statement; None for an unknown person."""
        own = select(
            literal(1).label("rank"),
            literal(0).label("position"),
            UserAssignment.no_ai.label("no_ai"),
            UserAssignment.connection_id.label("connection_id"),
            UserAssignment.model.label("model"),
        ).where(UserAssignment.org_id == self.org_id, UserAssignment.user_id == user_id)
        member = and_(
            GroupMember.group_id == GroupAssignment.group_id,
            GroupMember.member_type == PrincipalType.USER,
            GroupMember.member_id == user_id,
        )
        by_group = (
            select(
                literal(2),
                GroupAssignment.position,
                false(),
                GroupAssignment.connection_id,
                GroupAssignment.model,
            )
            .join(GroupMember, member)
            .where(GroupAssignment.org_id == self.org_id)
        )
        standard = select(
            literal(3), literal(0), false(), OrgAssignment.connection_id, OrgAssignment.model
        ).where(OrgAssignment.org_id == self.org_id, OrgAssignment.connection_id.is_not(None))
        candidates = union_all(own, by_group, standard).subquery()
        first = (
            select(candidates)
            .order_by(candidates.c.rank, candidates.c.position)
            .limit(1)
            .subquery()
        )
        stmt = (
            select(
                User.system_role,
                User.is_active,
                first.c.rank,
                func.coalesce(first.c.no_ai, false()),
                first.c.connection_id,
                first.c.model,
                AiConnection.enabled,
                AiConnection.purpose,
                AiConnection.models.has_key(first.c.model),
            )
            .select_from(User)
            .outerjoin(first, true())
            .outerjoin(AiConnection, AiConnection.id == first.c.connection_id)
            .where(User.org_id == self.org_id, User.id == user_id)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            return None
        role, active, rank, no_ai, connection_id, model, enabled, purpose, listed = row
        return Resolved(
            system_role=role,
            is_active=active,
            source=SOURCES.get(rank) if rank is not None else None,
            no_ai=bool(no_ai),
            connection_id=connection_id,
            model=model,
            connection_enabled=enabled,
            connection_purpose=purpose,
            model_listed=listed,
        )
