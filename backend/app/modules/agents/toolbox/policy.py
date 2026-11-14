"""How an agent may use each tool (plan M6 decision 2, spec 8.1 and 8.2).

- The agent's autonomy level (1 to 3 in M6; 4 comes with external tools, M8) sets the
  default per tool: `allow` from the tool's level up, `block` below it.
- Entries per agent and tool (`agent_tool`) can only tighten: the effective grant is
  the stricter of the default and the entry. An entry can never open a tool the level
  blocks, nor a tool the catalog does not list (those are never offered at all).
- A run offers the model only tools whose effective grant is `allow`. `confirm` needs
  the release flow of plan M6 task 7; until then a `confirm` tool is not offered
  (task 7 offers it and turns its call into a release request).
- A level above 2 is given only by an admin, or by someone who manages every space the
  agent is a member of (an agent without spaces: admins only).
"""

import uuid
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.modules.agents.repository import AgentRepository
from app.modules.agents.toolbox.base import Effect, Grant, ToolSpec

__all__ = [
    "FREE_LEVEL",
    "Effect",
    "Grant",
    "allowed",
    "default_grant",
    "effective",
    "may_grant_level",
]

FREE_LEVEL = 2  # up to this level anyone who may change the agent sets it


def default_grant(level: int, spec: ToolSpec) -> Grant:
    return Grant.ALLOW if level >= spec.level else Grant.BLOCK


def effective(level: int, spec: ToolSpec, entry: Grant | None) -> Grant:
    grant = default_grant(level, spec)
    if entry is not None and entry.strictness > grant.strictness:
        return entry
    return grant


def allowed(level: int, specs: list[ToolSpec], entries: Mapping[str, Grant]) -> list[ToolSpec]:
    """The tools a run may offer now (effective `allow`), in the catalog's order."""
    return [s for s in specs if effective(level, s, entries.get(s.name)) == Grant.ALLOW]


async def may_grant_level(
    session: AsyncSession, actor: Actor, agent_id: uuid.UUID | None, level: int
) -> bool:
    """Whether the actor may give the agent (None: one being created) the level."""
    if level <= FREE_LEVEL or actor.is_admin:
        return True
    if agent_id is None:
        return False
    spaces = await AgentRepository(session, actor.org_id).member_space_ids(agent_id)
    if not spaces:
        return False
    for space_id in spaces:
        if not await can(session, actor, Action.SPACE_MANAGE, space_id):
            return False
    return True
