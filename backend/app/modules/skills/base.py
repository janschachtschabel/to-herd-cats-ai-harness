"""What the skill services share: who sees skills at all, who manages one, the
repository for an actor, the input checks with their error codes, and the audit.

- Skills exist only for people with `ai.use` or `skill.manage`: everyone else gets 404
  `skill.not_found` from every skill route, as for an unknown id.
- Organisation-wide skills (no space) are read by all of them; a space's skills by
  those who may read the space (`visible_space_ids`, so a run's read scope narrows it
  too).
- Organisation-wide skills are managed with `skill.manage`; a space's skills with
  `page.moderate` in the space or `skill.manage`. A visible skill one may not manage
  answers 403 `auth.permission_denied`.
"""

import json
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, require, visible_space_ids
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.modules.audit.recorder import record
from app.modules.skills import format
from app.modules.skills.models import Skill
from app.modules.skills.repository import SkillRepository, SkillScope


def skill_not_found() -> NotFound:
    return NotFound(code="skill.not_found")


async def gate(session: AsyncSession, actor: Actor) -> None:
    """404 `skill.not_found` for those who see nothing about skills."""
    if await can(session, actor, Action.SKILL_MANAGE):
        return
    if not await can(session, actor, Action.AI_USE):
        raise skill_not_found()


def repo(session: AsyncSession, actor: Actor) -> SkillRepository:
    return SkillRepository(session, SkillScope(actor.org_id, visible_space_ids(actor)))


async def may_manage(session: AsyncSession, actor: Actor, space_id: uuid.UUID | None) -> bool:
    if await can(session, actor, Action.SKILL_MANAGE):
        return True
    return space_id is not None and await can(session, actor, Action.PAGE_MODERATE, space_id)


async def require_manage(session: AsyncSession, actor: Actor, space_id: uuid.UUID | None) -> None:
    """For a scope the actor sees: 403 unless it may manage skills there (a space it
    cannot read: 404 `space.not_found`, from `require`)."""
    if space_id is not None:
        await require(session, actor, Action.SPACE_READ, space_id)
    if not await may_manage(session, actor, space_id):
        raise Forbidden(code="auth.permission_denied")


async def visible(
    session: AsyncSession, actor: Actor, skill_id: uuid.UUID, *, lock: bool = False
) -> Skill:
    """The skill as the actor may see it (after the gate); 404 `skill.not_found` else.
    An admin who reaches a team or personal space's skill only by admin power is
    noted in the audit log, as for the space itself."""
    await gate(session, actor)
    skill = await repo(session, actor).get(skill_id, lock=lock)
    if skill is None:
        raise skill_not_found()
    if skill.space_id is not None:
        await require(session, actor, Action.SPACE_READ, skill.space_id)
    return skill


async def managed(session: AsyncSession, actor: Actor, skill_id: uuid.UUID, version: int) -> Skill:
    """The skill locked, if the actor may manage it (403 else), at `version` (409)."""
    skill = await visible(session, actor, skill_id, lock=True)
    if not await may_manage(session, actor, skill.space_id):
        raise Forbidden(code="auth.permission_denied")
    check_version(skill, version)
    return skill


def check_version(skill: Skill, version: int) -> None:
    if skill.version != version:
        raise Conflict(code="skill.version_conflict", details={"current_version": skill.version})


def _checked(check: Callable[[str], str], value: str) -> str:
    try:
        return check(value)
    except format.SkillFormatError as exc:
        raise ValidationFailed(code=f"skill.{exc.reason}") from None


def name(value: str) -> str:
    return _checked(format.checked_name, value)


def description(value: str) -> str:
    return _checked(format.checked_description, value)


def content(value: str) -> str:
    return _checked(format.checked_content, value)


async def unique_name(
    skills: SkillRepository, space_id: uuid.UUID | None, value: str, besides: uuid.UUID | None
) -> None:
    """409 `skill.name_taken` when another skill of the scope has the name (archived
    ones included). Holds the organisation's lock on skill names until the end of
    the transaction, so two writes cannot both find a name free."""
    await skills.lock_names()
    if await skills.name_taken(space_id, value, besides):
        raise Conflict(code="skill.name_taken")


async def audit(
    session: AsyncSession, actor: Actor, action: str, skill_id: uuid.UUID, details: dict[str, Any]
) -> None:
    plain = json.loads(json.dumps(details, default=str))  # ids as text
    await record(session, actor, action, "skill", skill_id, plain)
