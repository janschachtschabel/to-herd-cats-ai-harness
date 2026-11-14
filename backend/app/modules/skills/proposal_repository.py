"""The SQL of skill proposals: who sees which (`sight.seen`), the list, locking, and
what the handler asks (no actor: the event's organisation). Every statement starts
from the organisation."""

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ADMIN_ROLES
from app.modules.skills.models import Skill, SkillVersion
from app.modules.skills.proposal_models import SkillProposal, SkillProposalState
from app.modules.skills.sight import SkillProposalSight, seen
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class SkillProposalFilter:
    space_id: uuid.UUID | None = None
    org_wide: bool | None = None  # True: only organisation-wide; False: only spaces'
    state: SkillProposalState | None = None


def visible(sight: SkillProposalSight) -> ColumnElement[bool]:
    return and_(
        SkillProposal.org_id == sight.org_id,
        seen(sight, SkillProposal.space_id, SkillProposal.author_type, SkillProposal.author_id),
    )


class SkillProposalRepository:
    def __init__(self, session: AsyncSession, sight: SkillProposalSight) -> None:
        self.session = session
        self.sight = sight

    async def add(self, proposal: SkillProposal) -> SkillProposal:
        self.session.add(proposal)
        await self.session.flush()
        return proposal

    async def get(self, proposal_id: uuid.UUID, *, lock: bool = False) -> SkillProposal | None:
        stmt = (
            select(SkillProposal)
            .where(visible(self.sight), SkillProposal.id == proposal_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def page(
        self, where: SkillProposalFilter, before: uuid.UUID | None, limit: int
    ) -> list[SkillProposal]:
        """Newest first."""
        stmt = select(SkillProposal).where(visible(self.sight))
        if where.space_id is not None:
            stmt = stmt.where(SkillProposal.space_id == where.space_id)
        if where.org_wide is True:
            stmt = stmt.where(SkillProposal.space_id.is_(None))
        elif where.org_wide is False:
            stmt = stmt.where(SkillProposal.space_id.is_not(None))
        if where.state is not None:
            stmt = stmt.where(SkillProposal.state == where.state)
        if before is not None:
            stmt = stmt.where(SkillProposal.id < before)
        stmt = stmt.order_by(SkillProposal.id.desc()).limit(limit)
        return list(await self.session.scalars(stmt))


class SkillProposalFacts:
    """Lookups within one organisation, after the caller's check, and for the
    handler."""

    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def proposal(self, proposal_id: uuid.UUID) -> SkillProposal | None:
        stmt = select(SkillProposal).where(
            SkillProposal.org_id == self.org_id, SkillProposal.id == proposal_id
        )
        return await self.session.scalar(stmt)

    async def newest_number(self, skill_id: uuid.UUID) -> int:
        """The number of the skill's newest version (0 without one)."""
        number = await self.session.scalar(
            select(func.coalesce(func.max(SkillVersion.number), 0)).where(
                SkillVersion.org_id == self.org_id, SkillVersion.skill_id == skill_id
            )
        )
        return int(number or 0)

    async def skill_names(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not ids:
            return {}
        stmt = select(Skill.id, Skill.name).where(Skill.org_id == self.org_id, Skill.id.in_(ids))
        return {row[0]: row[1] for row in await self.session.execute(stmt)}

    async def version_numbers(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not ids:
            return {}
        stmt = select(SkillVersion.id, SkillVersion.number).where(
            SkillVersion.org_id == self.org_id, SkillVersion.id.in_(ids)
        )
        return {row[0]: row[1] for row in await self.session.execute(stmt)}

    async def administrators(self) -> list[uuid.UUID]:
        """The active owners and admins (who hold `skill.manage`)."""
        stmt = (
            select(User.id)
            .where(
                User.org_id == self.org_id,
                User.is_active.is_(True),
                User.system_role.in_([r.value for r in ADMIN_ROLES]),
            )
            .order_by(User.id)
        )
        return list((await self.session.scalars(stmt)).all())
