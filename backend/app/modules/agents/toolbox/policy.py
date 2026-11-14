"""How an agent may use each tool (plan M6 decision 2, spec 8.1 and 8.2).

- The agent's autonomy level (1 to 3 in M6; 4 comes with external tools, M8) sets the
  default per tool: `allow` from the tool's level up, `block` below it.
- Entries per agent and tool (`agent_tool`) can only tighten: the effective grant is
  the stricter of the default and the entry. An entry can never open a tool the level
  blocks, nor a tool the catalog does not list (those are never offered at all).
- A run offers the model the tools whose effective grant is `allow` or `confirm`; a
  call of a `confirm` tool waits for a person's release (`approvals/gate.py`, plan M6
  task 7). `block` is never offered.
- A level above 2 is given only by an admin. (Spec 8.2 also names whoever manages every
  space of the agent; but changing an organisation's agent at all needs
  `agent.manage`, which only admins hold, and a personal agent stays at 2, so that
  rule has no caller here.)
"""

from collections.abc import Mapping

from app.core.access import Actor
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
    """The tools a run may offer now (effective `allow` or `confirm`), in the catalog's
    order."""
    return [s for s in specs if effective(level, s, entries.get(s.name)) != Grant.BLOCK]


def may_grant_level(actor: Actor, level: int) -> bool:
    """Whether the actor may give an agent the level."""
    return level <= FREE_LEVEL or actor.is_admin
