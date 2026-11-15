"""What the host adds to a run's instructions before its first model call (spec 8.3
point 2): the skills the run may load (`toolbox/skill_tools.listing`: names and
descriptions only) and the agent's memory pages it may read (`memory.for_run`, at
most 4,000 characters together). Decided anew at every take-up, with the run's actor
as it is then and its connection's data location; the memory's spaces and pages are
what the run has read (the caller adds them to its reads)."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.modules.agents import memory
from app.modules.agents.models import Agent
from app.modules.agents.toolbox.skill_tools import listing
from app.modules.ai.models import DataLocation
from app.modules.skills.runs import skills_for_run


@dataclass(frozen=True, slots=True)
class Briefing:
    sections: list[str]
    spaces: frozenset[uuid.UUID]  # read for it (the memory pages' spaces)
    pages: frozenset[uuid.UUID]


async def brief(
    session: AsyncSession,
    actor: Actor,
    agent: Agent,
    location: DataLocation,
    place_space: uuid.UUID | None,
) -> Briefing:
    skills = listing(await skills_for_run(session, actor, agent.id, location))
    remembered = await memory.for_run(session, actor, agent.id, location, place_space)
    sections = [s for s in (skills, remembered.text) if s is not None]
    return Briefing(sections, remembered.spaces, remembered.pages)
