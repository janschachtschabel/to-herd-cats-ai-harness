"""People and groups by name, for pickers: one query over both, sorted by name."""

import uuid
from typing import NamedTuple

from sqlalchemy import String, func, literal, select, tuple_, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_repository import person_reads_space
from app.core.principal import PrincipalType
from app.modules.groups.models import Group
from app.modules.users.models import User


class DirectoryEntry(NamedTuple):
    type: PrincipalType
    id: uuid.UUID
    name: str
    key: str  # the sort key (lower-cased name), for the cursor


class DirectoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        org_id: uuid.UUID,
        text: str,
        types: frozenset[PrincipalType],
        after: tuple[str, uuid.UUID] | None,
        limit: int,
        space_id: uuid.UUID | None = None,
    ) -> list[DirectoryEntry]:
        """Active people and groups whose name contains `text`; case-insensitive, `%`
        and `_` taken literally. Never the email: members must not probe addresses.
        With `space_id`, only the people who may read that space."""
        parts = []
        if PrincipalType.USER in types:
            people = select(
                literal(PrincipalType.USER.value, String).label("type"),
                User.id.label("id"),
                User.name.label("name"),
            ).where(
                User.org_id == org_id,
                User.is_active.is_(True),
                User.name.icontains(text, autoescape=True),
            )
            if space_id is not None:
                people = people.where(person_reads_space(literal(space_id)))
            parts.append(people)
        if PrincipalType.GROUP in types:
            parts.append(
                select(
                    literal(PrincipalType.GROUP.value, String).label("type"),
                    Group.id.label("id"),
                    Group.name.label("name"),
                ).where(Group.org_id == org_id, Group.name.icontains(text, autoescape=True))
            )
        if not parts:
            return []
        both = union_all(*parts).subquery()
        key = func.lower(both.c.name)
        stmt = select(both.c.type, both.c.id, both.c.name, key).order_by(key, both.c.id)
        if after is not None:
            stmt = stmt.where(tuple_(key, both.c.id) > tuple_(literal(after[0]), after[1]))
        rows = (await self.session.execute(stmt.limit(limit))).all()
        return [DirectoryEntry(PrincipalType(t), i, n, k) for t, i, n, k in rows]
