"""What the host adds to a run's instructions before its first model call (spec 8.3
point 2): the skills the run may load (`toolbox/skill_tools.listing`: names and
descriptions only). Decided anew at every take-up, with the run's actor as it is
then and its connection's data location."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.modules.agents.models import Agent
from app.modules.agents.toolbox.skill_tools import listing
from app.modules.ai.models import DataLocation
from app.modules.skills.runs import skills_for_run


async def sections(
    session: AsyncSession, actor: Actor, agent: Agent, location: DataLocation
) -> list[str]:
    skills = listing(await skills_for_run(session, actor, agent.id, location))
    return [skills] if skills is not None else []
