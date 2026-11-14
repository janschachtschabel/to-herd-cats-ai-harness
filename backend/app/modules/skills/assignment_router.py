"""An agent's skills (`agent.manage`; 404 `agent.not_found` else). A bounded set (at
most 50), shown and replaced whole like the agent's tools, so not paginated."""

import uuid
from typing import Annotated, Self

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.core.access import Actor
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.skills.assignments import MAX_AGENT_SKILLS, AgentSkills, AgentSkillSet
from app.modules.skills.schemas import SkillOut
from app.modules.skills.service import SkillService

agent_skills = APIRouter(prefix="/agents/{agent_id}/skills", tags=["skills"])


class AgentSkillOut(SkillOut):
    """`available`: whether the agent may use it now (active, and organisation-wide or
    of a space the agent reads); a run also needs the person and the place to read it."""

    available: bool


class AgentSkillsOut(BaseModel):
    """`version`: the agent's (setting the skills changes it)."""

    version: int
    skills: list[AgentSkillOut]

    @classmethod
    async def of(cls, session: SessionDep, actor: Actor, shown: AgentSkillSet) -> Self:
        names = await SkillService(session).authors(actor, [s.skill for s in shown.skills])
        skills = [
            AgentSkillOut(**SkillOut.fields(s.skill, names), available=s.available)
            for s in shown.skills
        ]
        return cls(version=shown.agent.version, skills=skills)


class AgentSkillsPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_ids: Annotated[list[uuid.UUID], Field(max_length=MAX_AGENT_SKILLS)]
    version: int


@agent_skills.get("", response_model=AgentSkillsOut)
async def get_agent_skills(
    agent_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> AgentSkillsOut:
    """The agent's skills the caller sees, by name."""
    return await AgentSkillsOut.of(session, actor, await AgentSkills(session).get(actor, agent_id))


@agent_skills.put("", response_model=AgentSkillsOut)
async def set_agent_skills(
    agent_id: uuid.UUID, body: AgentSkillsPut, actor: ActorDep, session: SessionDep
) -> AgentSkillsOut:
    """Replace the agent's skills (those the caller sees), with the agent's `version`."""
    shown = await AgentSkills(session).replace(actor, agent_id, body.skill_ids, body.version)
    return await AgentSkillsOut.of(session, actor, shown)
