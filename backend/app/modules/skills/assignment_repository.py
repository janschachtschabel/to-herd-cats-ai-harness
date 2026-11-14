"""The SQL of agents' skills (`agent_skill`): what an agent has, as its manager sees
it; replacing that; and what a run may use. Every statement starts from the
organisation."""

import uuid
from collections.abc import Collection

from sqlalchemy import Select, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.skills.models import AgentSkill, Skill, SkillState
from app.modules.skills.repository import SkillScope, visible


class AgentSkillRepository:
    def __init__(self, session: AsyncSession, scope: SkillScope) -> None:
        self.session = session
        self.scope = scope

    def _assigned(self, agent_id: uuid.UUID) -> Select[Skill]:
        return (
            select(Skill)
            .join(AgentSkill, AgentSkill.skill_id == Skill.id)
            .where(
                AgentSkill.org_id == self.scope.org_id,
                AgentSkill.agent_id == agent_id,
                visible(self.scope),
            )
        )

    async def assigned(self, agent_id: uuid.UUID) -> list[Skill]:
        """The agent's skills the scope sees, by name."""
        stmt = self._assigned(agent_id).order_by(Skill.name, Skill.id)
        return list(await self.session.scalars(stmt))

    async def seen(self, skill_ids: Collection[uuid.UUID]) -> list[Skill]:
        """Those of `skill_ids` the scope sees."""
        if not skill_ids:
            return []
        stmt = select(Skill).where(visible(self.scope), Skill.id.in_(skill_ids))
        return list(await self.session.scalars(stmt))

    async def replace(self, agent_id: uuid.UUID, skill_ids: Collection[uuid.UUID]) -> None:
        """The agent's skills the scope sees become `skill_ids`; others stay."""
        seen = select(Skill.id).where(visible(self.scope))
        await self.session.execute(
            delete(AgentSkill).where(
                AgentSkill.org_id == self.scope.org_id,
                AgentSkill.agent_id == agent_id,
                AgentSkill.skill_id.in_(seen),
            )
        )
        for skill_id in sorted(skill_ids):
            self.session.add(
                AgentSkill(org_id=self.scope.org_id, agent_id=agent_id, skill_id=skill_id)
            )
        await self.session.flush()

    async def usable(
        self,
        agent_id: uuid.UUID,
        ai_space_ids: Select[uuid.UUID],
        name: str | None = None,
    ) -> list[Skill]:
        """The agent's active skills the scope sees that are organisation-wide or in
        a space of `ai_space_ids` (whose AI policy lets the run's connection receive
        them); with `name`, only those of that name. By name, then id."""
        stmt = self._assigned(agent_id).where(
            Skill.state == SkillState.ACTIVE,
            or_(Skill.space_id.is_(None), Skill.space_id.in_(ai_space_ids)),
        )
        if name is not None:
            stmt = stmt.where(Skill.name == name)
        stmt = stmt.order_by(Skill.name, Skill.id)
        return list(await self.session.scalars(stmt))
