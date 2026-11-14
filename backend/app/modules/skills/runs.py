"""What a run may use of its agent's skills (plan M6 decision 11), for the agent's
context (names and descriptions only) and for `load_skill` (the text).

Decided at use time, with the run's actor (`agents/actor.py`: the person who asked,
held to what the agent may read and to the audience of the run's place) and the
data location of the run's connection. A skill is usable when it is assigned to the
agent and active, and organisation-wide or in a space that the actor reads (its
read scope included) and whose AI policy lets that connection receive it
(`ai/policy_filters.ai_space_ids`). So an assignment whose space the agent left, or
that the person cannot read, stays without effect; nothing has to be cleaned up.

A name two usable skills share (an organisation-wide skill and a renamed space skill)
is left out of both: the run could not tell which one it loads.

Callers pass the actor of a run that may go on (`allowed_actor`); these functions
check nothing about the person or the agent beyond the skills themselves. Each
answer names the skill's space (None: organisation-wide), for the caller to track
what the run read.
"""

import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor, visible_space_ids
from app.modules.ai.models import DataLocation
from app.modules.ai.policy_filters import ai_space_ids
from app.modules.skills.assignment_repository import AgentSkillRepository
from app.modules.skills.models import Skill
from app.modules.skills.repository import SkillScope


@dataclass(frozen=True, slots=True)
class RunSkill:
    id: uuid.UUID
    name: str
    description: str
    space_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class LoadedSkill:
    id: uuid.UUID
    name: str
    description: str
    content: str
    space_id: uuid.UUID | None


def _repo(session: AsyncSession, actor: Actor) -> AgentSkillRepository:
    return AgentSkillRepository(session, SkillScope(actor.org_id, visible_space_ids(actor)))


def _unique(skills: list[Skill]) -> list[Skill]:
    counts = Counter(s.name for s in skills)
    return [s for s in skills if counts[s.name] == 1]


async def skills_for_run(
    session: AsyncSession, actor: Actor, agent_id: uuid.UUID, location: DataLocation
) -> list[RunSkill]:
    """The skills the run may use, by name: name, description and space only."""
    usable = await _repo(session, actor).usable(agent_id, ai_space_ids(actor.org_id, location))
    return [RunSkill(s.id, s.name, s.description, s.space_id) for s in _unique(usable)]


async def load_for_run(
    session: AsyncSession,
    actor: Actor,
    agent_id: uuid.UUID,
    location: DataLocation,
    name: str,
) -> LoadedSkill | None:
    """The skill of that name with its text, if the run may use it (None else)."""
    usable = await _repo(session, actor).usable(
        agent_id, ai_space_ids(actor.org_id, location), name=name
    )
    found = _unique(usable)
    if not found:
        return None
    skill = found[0]
    return LoadedSkill(skill.id, skill.name, skill.description, skill.content, skill.space_id)
