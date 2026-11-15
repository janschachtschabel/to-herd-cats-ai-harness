"""How an agent may use each tool (plan M6 decision 2, spec 8.1 and 8.2).

- The agent's autonomy level (1 to 4) sets the default per tool: `allow` from the
  tool's level up, `block` below it. Level 4 (acting outside, plan M8 decision 8) adds
  the external write tools, which are never looser than `confirm` (`ToolSpec.floor`).
- External tools (`ToolSpec.explicit`) are offered only to an agent with an entry for
  each: without one they are `block`; with one, the stricter of the entry and what
  the level allows (an external read tool is level 2, a write tool level 4).
- Entries per agent and tool (`agent_tool`) can only tighten: the effective grant is
  the stricter of the default and the entry. An entry can never open a tool the level
  blocks, nor a tool the catalog does not list (those are never offered at all).
- A run offers the model the tools whose effective grant is `allow` or `confirm`; a
  call of a `confirm` tool waits for a person's release (`approvals/gate.py`, plan M6
  task 7). `block` is never offered.
- In an event rule's run (`watched`) a tool of level 3 (`UNWATCHED_LEVEL`: a direct
  write) whose grant is `allow` becomes `confirm`: the text of whoever caused the
  event reaches the model with the owner's rights, so the owner releases each such
  call (review M7, finding 8). Level 2 (tickets, comments, proposals) stays as
  granted, so chains of rules go on; the run's own answer is no tool call.
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
    "watched",
]

FREE_LEVEL = 2  # up to this level anyone who may change the agent sets it
UNWATCHED_LEVEL = 3  # from this level a tool writes directly (spec 8.2)


def ceiling(level: int, spec: ToolSpec) -> Grant:
    """The loosest grant the level allows for the tool."""
    return spec.floor if level >= spec.level else Grant.BLOCK


def default_grant(level: int, spec: ToolSpec) -> Grant:
    """The grant without an entry (an external tool: none)."""
    return Grant.BLOCK if spec.explicit else ceiling(level, spec)


def effective(level: int, spec: ToolSpec, entry: Grant | None) -> Grant:
    if entry is None:
        return default_grant(level, spec)
    grant = ceiling(level, spec)
    return entry if entry.strictness > grant.strictness else grant


def watched(grant: Grant, spec: ToolSpec, *, event_rule: bool) -> Grant:
    """The grant in a run: in an event rule's run a direct write that is `allow` asks
    its owner (`confirm`)."""
    if event_rule and spec.level >= UNWATCHED_LEVEL and grant == Grant.ALLOW:
        return Grant.CONFIRM
    return grant


def allowed(level: int, specs: list[ToolSpec], entries: Mapping[str, Grant]) -> list[ToolSpec]:
    """The tools a run may offer now (effective `allow` or `confirm`), in the catalog's
    order."""
    return [s for s in specs if effective(level, s, entries.get(s.name)) != Grant.BLOCK]


def may_grant_level(actor: Actor, level: int) -> bool:
    """Whether the actor may give an agent the level."""
    return level <= FREE_LEVEL or actor.is_admin
