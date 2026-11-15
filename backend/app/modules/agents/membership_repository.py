"""The SQL of an agent's memberships as its managers see them (`memberships.py`)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import SpaceRole
from app.core.principal import PrincipalType
from app.modules.spaces.models import Space, SpaceKind, SpaceMember


@dataclass(frozen=True, slots=True)
class AgentSpace:
    id: uuid.UUID
    name: str
    kind: SpaceKind
    role: SpaceRole


class AgentSpaceRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def page(
        self, agent_id: uuid.UUID, after: tuple[str, uuid.UUID] | None, limit: int
    ) -> list[AgentSpace]:
        stmt = (
            select(Space.id, Space.name, Space.kind, SpaceMember.role)
            .join(SpaceMember, SpaceMember.space_id == Space.id)
            .where(
                Space.org_id == self.org_id,
                SpaceMember.member_type == PrincipalType.AGENT,
                SpaceMember.member_id == agent_id,
            )
            .order_by(Space.name, Space.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(tuple_(Space.name, Space.id) > tuple_(*after))
        rows = await self.session.execute(stmt)
        return [AgentSpace(r.id, r.name, SpaceKind(r.kind), SpaceRole(r.role)) for r in rows]
