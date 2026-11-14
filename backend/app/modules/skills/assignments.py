"""An agent's skills as its managers see and set them (plan M6 decision 11): holders of
`agent.manage` only (404 `agent.not_found` else, as for the agent's other settings).

Setting replaces the agent's skills at once, with the agent's `version` (409
`agent.version_conflict`), at most `MAX_AGENT_SKILLS`. Only skills the caller sees
can be given, and only organisation-wide ones or those of a space the agent reads
(its memberships and the open spaces); anything else, an unknown id included, is
422 `agent.skill_not_assignable` with the ids. Two skills of one name are 422
`agent.skill_names_clash` (a run asks for a skill by its name). Skills the caller
does not see are neither shown nor touched. Every change is audited (the ids).

Whether a run may use an assigned skill is decided when it does (`runs.py`):
`available` says whether the agent itself still may (active, and organisation-wide
or in a space it reads), so a skill whose space the agent left shows up as such.
"""

import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor, visible_space_ids
from app.core.errors import ValidationFailed
from app.modules.agents.models import Agent
from app.modules.agents.repository import AgentRepository
from app.modules.agents.service import AgentService
from app.modules.audit.recorder import record
from app.modules.skills.assignment_repository import AgentSkillRepository
from app.modules.skills.models import Skill, SkillState
from app.modules.skills.repository import SkillScope

MAX_AGENT_SKILLS = 50


@dataclass(frozen=True, slots=True)
class AssignedSkill:
    skill: Skill
    available: bool


@dataclass(frozen=True, slots=True)
class AgentSkillSet:
    agent: Agent
    skills: list[AssignedSkill]


class AgentSkills:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.agents = AgentService(session)

    def repo(self, actor: Actor) -> AgentSkillRepository:
        scope = SkillScope(actor.org_id, visible_space_ids(actor))
        return AgentSkillRepository(self.session, scope)

    async def get(self, actor: Actor, agent_id: uuid.UUID) -> AgentSkillSet:
        agent = await self.agents.get(actor, agent_id)
        return await self._shown(actor, agent)

    async def replace(
        self, actor: Actor, agent_id: uuid.UUID, skill_ids: Sequence[uuid.UUID], version: int
    ) -> AgentSkillSet:
        await self.agents.get(actor, agent_id)  # 404 for those who do not manage agents
        wanted = set(skill_ids)
        if len(wanted) > MAX_AGENT_SKILLS:
            raise ValidationFailed(code="validation_failed")
        repo = self.repo(actor)
        found = {s.id: s for s in await repo.seen(wanted)}
        reach = await self._reach(actor, agent_id)
        refused = sorted(str(i) for i in wanted if i not in found or not _within(found[i], reach))
        if refused:
            raise ValidationFailed(
                code="agent.skill_not_assignable", details={"skill_ids": refused}
            )
        clashes = sorted(n for n, k in Counter(s.name for s in found.values()).items() if k > 1)
        if clashes:
            raise ValidationFailed(code="agent.skill_names_clash", details={"names": clashes})
        agent = await self.agents.current(actor, agent_id, version)
        await repo.replace(agent.id, wanted)
        agent.version += 1
        await self.session.flush()
        details = {"skill_ids": sorted(str(i) for i in wanted)}
        await record(self.session, actor, "agent.skills_changed", "agent", agent.id, details)
        return await self._shown(actor, agent)

    async def _reach(self, actor: Actor, agent_id: uuid.UUID) -> set[uuid.UUID]:
        """The spaces the agent reads."""
        return set(await AgentRepository(self.session, actor.org_id).roles(agent_id))

    async def _shown(self, actor: Actor, agent: Agent) -> AgentSkillSet:
        reach = await self._reach(actor, agent.id)
        skills = await self.repo(actor).assigned(agent.id)
        shown = [
            AssignedSkill(s, s.state == SkillState.ACTIVE and _within(s, reach)) for s in skills
        ]
        return AgentSkillSet(agent, shown)


def _within(skill: Skill, reach: set[uuid.UUID]) -> bool:
    return skill.space_id is None or skill.space_id in reach
