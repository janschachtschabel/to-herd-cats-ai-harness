"""A skill's versions: listed newest first and read by whoever reads the skill;
restored by whoever manages it. Restoring makes a new version with the old
description and content (history is never rewritten), with the skill's `version`
(409 `skill.version_conflict`). A number the skill does not have: 404
`skill.version_not_found`."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Actor
from app.core.errors import NotFound
from app.core.pagination import PageParams, decode_id_cursor, id_page
from app.modules.skills import base
from app.modules.skills.models import Skill, SkillVersion


def version_not_found() -> NotFound:
    return NotFound(code="skill.version_not_found")


class SkillVersions:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, actor: Actor, skill_id: uuid.UUID, params: PageParams
    ) -> pagination.Page[SkillVersion]:
        skill = await base.visible(self.session, actor, skill_id)
        before = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await base.repo(self.session, actor).versions(skill.id, before, params.limit + 1)
        return id_page(rows, params.limit, lambda v: v.id)

    async def get(self, actor: Actor, skill_id: uuid.UUID, number: int) -> SkillVersion:
        skill = await base.visible(self.session, actor, skill_id)
        found = await base.repo(self.session, actor).version(skill.id, number)
        if found is None:
            raise version_not_found()
        return found

    async def restore(self, actor: Actor, skill_id: uuid.UUID, number: int, version: int) -> Skill:
        skill = await base.managed(self.session, actor, skill_id, version)
        skills = base.repo(self.session, actor)
        old = await skills.version(skill.id, number)
        if old is None:
            raise version_not_found()
        skill.description, skill.content = old.description, old.content
        made = await skills.add_version(skill, actor.principal)
        skill.version += 1
        await self.session.flush()
        details = {"from_number": number, "version_number": made.number}
        await base.audit(self.session, actor, "skill.restored", skill.id, details)
        return skill
