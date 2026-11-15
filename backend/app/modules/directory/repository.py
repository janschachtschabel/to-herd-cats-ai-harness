"""People, groups and (for those with `ai.use`) agents by name, for pickers: one query
over all of them, sorted by name."""

import uuid
from typing import NamedTuple

from sqlalchemy import String, func, literal, or_, select, tuple_, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_repository import person_reads_space
from app.core.principal import PrincipalType
from app.modules.agents.models import Agent, AgentKind, AgentStatus
from app.modules.groups.models import Group
from app.modules.spaces.models import SpaceMember
from app.modules.users.models import User


class DirectoryEntry(NamedTuple):
    type: PrincipalType
    id: uuid.UUID
    name: str
    key: str  # the sort key (lower-cased name), for the cursor
    kind: AgentKind | None = None  # an agent's kind (plan M8); None for people and groups


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
        viewer: uuid.UUID | None = None,
    ) -> list[DirectoryEntry]:
        """Active people, groups and agents that are not drafts, whose name contains
        `text`; case-insensitive, `%` and `_` taken literally. Never the email: members
        must not probe addresses.
        With `space_id`, only the people who may read that space and the agents that
        are its members. Personal agents only for their owner (`viewer`), never for
        anyone else."""
        parts = []
        if PrincipalType.USER in types:
            people = select(
                literal(PrincipalType.USER.value, String).label("type"),
                User.id.label("id"),
                User.name.label("name"),
                literal(None, String).label("kind"),
            ).where(
                User.org_id == org_id,
                User.is_active.is_(True),
                User.name.icontains(text, autoescape=True),
            )
            if space_id is not None:
                people = people.where(person_reads_space(literal(space_id)))
            parts.append(people)
        if PrincipalType.AGENT in types:
            agents = select(
                literal(PrincipalType.AGENT.value, String).label("type"),
                Agent.id.label("id"),
                Agent.name.label("name"),
                Agent.kind.label("kind"),
            ).where(
                Agent.org_id == org_id,
                Agent.status != AgentStatus.DRAFT,
                Agent.name.icontains(text, autoescape=True),
                or_(Agent.owner_user_id.is_(None), Agent.owner_user_id == viewer),
            )
            if space_id is not None:
                member = select(SpaceMember.member_id).where(
                    SpaceMember.space_id == space_id,
                    SpaceMember.member_type == PrincipalType.AGENT,
                    SpaceMember.member_id == Agent.id,
                )
                agents = agents.where(member.exists())
            parts.append(agents)
        if PrincipalType.GROUP in types:
            parts.append(
                select(
                    literal(PrincipalType.GROUP.value, String).label("type"),
                    Group.id.label("id"),
                    Group.name.label("name"),
                    literal(None, String).label("kind"),
                ).where(Group.org_id == org_id, Group.name.icontains(text, autoescape=True))
            )
        if not parts:
            return []
        both = union_all(*parts).subquery()
        key = func.lower(both.c.name)
        stmt = select(both.c.type, both.c.id, both.c.name, key, both.c.kind).order_by(
            key, both.c.id
        )
        if after is not None:
            stmt = stmt.where(tuple_(key, both.c.id) > tuple_(literal(after[0]), after[1]))
        rows = (await self.session.execute(stmt.limit(limit))).all()
        return [
            DirectoryEntry(PrincipalType(t), i, n, k, AgentKind(kind) if kind else None)
            for t, i, n, k, kind in rows
        ]
