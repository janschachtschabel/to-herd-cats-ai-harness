"""Who sees a skill proposal (plan M6 task 9): one rule, for the proposal routes
(`proposal_repository.py`) and for the activity entries about one
(`messaging/activity_repository.py`, which passes its own columns).

- Nobody without `ai.use` or `skill.manage` (as for skills, `base.gate`).
- Its space must be one the actor reads (an organisation-wide proposal has none).
- Then: whoever may decide it (`skill.manage`; for a space's proposal also
  `page.moderate` there), and its author for their own.

Imports nothing of messaging, so messaging may import it.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, false, or_, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, space_ids_with, visible_space_ids
from app.core.principal import Principal


@dataclass(frozen=True, slots=True)
class SkillProposalSight:
    org_id: uuid.UUID
    principal: Principal
    sees_skills: bool  # `ai.use` or `skill.manage`: else nothing at all
    manages_all: bool  # `skill.manage`
    space_ids: Select[uuid.UUID]  # the spaces the actor reads
    moderated_ids: Select[uuid.UUID]  # those where it holds `page.moderate`


async def sight_of(session: AsyncSession, actor: Actor) -> SkillProposalSight:
    manages_all = await can(session, actor, Action.SKILL_MANAGE)
    sees = manages_all or await can(session, actor, Action.AI_USE)
    return SkillProposalSight(
        actor.org_id,
        actor.principal,
        sees,
        manages_all,
        visible_space_ids(actor),
        space_ids_with(actor, Action.PAGE_MODERATE),
    )


def seen(
    sight: SkillProposalSight, space_id: Any, author_type: Any, author_id: Any
) -> ColumnElement[bool]:
    """The rule over a proposal's columns (its space, its author)."""
    if not sight.sees_skills:
        return false()
    readable = or_(space_id.is_(None), space_id.in_(sight.space_ids))
    decides = true() if sight.manages_all else space_id.in_(sight.moderated_ids)
    own = and_(author_type == sight.principal.type, author_id == sight.principal.id)
    return and_(readable, or_(decides, own))
