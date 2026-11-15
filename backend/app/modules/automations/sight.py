"""Who may see an automation (plan M7 decision 12; the management routes come with
task 7): one rule, here for the activity entries about one
(`messaging/activity_repository.py`, which passes its own columns), so an entry is
listed only while its recipient may still see what it names.

- Whoever holds `agent.manage` sees every automation of the organisation.
- Otherwise nobody without `ai.use` (who sees no agents at all), and then: its owner,
  the agent's responsible person, and the people who manage the space of its place
  (`space.manage` there; a DM has no space).

`seen` is the rule over an automation's columns (lists, activity); `sees` asks it of
one automation's values (its live events).

Imports nothing of messaging, so messaging may import it.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, false, literal, or_, select, true
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, space_ids_with


@dataclass(frozen=True, slots=True)
class AutomationSight:
    person_id: uuid.UUID
    sees: bool  # `ai.use` or `agent.manage`: else nothing at all
    manages_all: bool  # `agent.manage`
    managed_ids: Select[uuid.UUID]  # the spaces where it holds `space.manage`


async def sight_of(session: AsyncSession, actor: Actor) -> AutomationSight:
    manages_all = await can(session, actor, Action.AGENT_MANAGE)
    sees = manages_all or await can(session, actor, Action.AI_USE)
    return AutomationSight(
        actor.principal.id, sees, manages_all, space_ids_with(actor, Action.SPACE_MANAGE)
    )


def seen(
    sight: AutomationSight, owner_id: Any, responsible_id: Any, space_id: Any
) -> ColumnElement[bool]:
    """The rule over an automation's columns: its owner, its agent's responsible
    person, the space of its place (NULL for a DM)."""
    if not sight.sees:
        return false()
    if sight.manages_all:
        return true()
    return or_(
        owner_id == sight.person_id,
        responsible_id == sight.person_id,
        space_id.in_(sight.managed_ids),
    )


async def sees(
    session: AsyncSession,
    sight: AutomationSight,
    owner_id: uuid.UUID,
    responsible_id: uuid.UUID | None,
    space_id: uuid.UUID | None,
) -> bool:
    """The rule (`seen`) for one automation's values."""
    rule = seen(
        sight,
        literal(owner_id, PG_UUID(as_uuid=True)),
        literal(responsible_id, PG_UUID(as_uuid=True)),
        literal(space_id, PG_UUID(as_uuid=True)),
    )
    return bool(await session.scalar(select(rule)))
