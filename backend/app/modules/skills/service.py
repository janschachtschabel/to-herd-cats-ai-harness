"""Skills (spec 11, plan M6 decision 11): listing, reading, making, changing,
archiving. Who sees and manages which: `base.py`. Versions: `versions.py`; import
and export: `transfer.py`; agents' skills: `assignments.py`; what a run may use:
`runs.py`.

A skill is made with its first version; every change of description or content
makes the next one (a rename does not: the name is no part of the text). Writes
carry the skill's `version` (409 `skill.version_conflict`). Skills are archived,
never deleted (an archived skill keeps its name, its versions and its assignments,
and no run uses it). Every change is audited with names, lengths and numbers, never
the skill's text.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require
from app.core.errors import Conflict
from app.core.pagination import PageParams, decode_key_cursor, encode_key_cursor
from app.core.principal import Principal, PrincipalType
from app.modules.skills import base
from app.modules.skills.models import Skill, SkillState, SkillVersion
from app.modules.skills.repository import SkillFilter


@dataclass(frozen=True, slots=True)
class SkillDraft:
    name: str
    description: str
    content: str
    space_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class SkillChange:
    version: int
    name: str | None = None
    description: str | None = None
    content: str | None = None


class SkillService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, actor: Actor, where: SkillFilter, params: PageParams
    ) -> pagination.Page[Skill]:
        """By name. A space filter for a space one cannot read: 404 `space.not_found`."""
        await base.gate(self.session, actor)
        if where.space_id is not None:
            await require(self.session, actor, Action.SPACE_READ, where.space_id)
        after = decode_key_cursor(params.cursor) if params.cursor else None
        rows = await base.repo(self.session, actor).page(where, after, params.limit + 1)
        items = rows[: params.limit]
        more = len(rows) > params.limit
        cursor = encode_key_cursor(items[-1].name, items[-1].id) if more else None
        return pagination.Page[Skill](items=items, next_cursor=cursor)

    async def get(self, actor: Actor, skill_id: uuid.UUID) -> Skill:
        return await base.visible(self.session, actor, skill_id)

    async def create(
        self, actor: Actor, draft: SkillDraft, author: Principal | None = None
    ) -> Skill:
        """`author` defaults to the actor (an import names the actor too)."""
        await base.gate(self.session, actor)
        await base.require_manage(self.session, actor, draft.space_id)
        name = base.name(draft.name)
        description = base.description(draft.description)
        content = base.content(draft.content)
        skills = base.repo(self.session, actor)
        await base.unique_name(skills, draft.space_id, name, None)
        who = author or actor.principal
        skill = await skills.add(
            Skill(
                org_id=actor.org_id,
                space_id=draft.space_id,
                name=name,
                description=description,
                content=content,
                state=SkillState.ACTIVE,
                author_type=who.type,
                author_id=who.id,
            )
        )
        await skills.add_version(skill, who)
        details = {
            "name": name,
            "space_id": draft.space_id,
            "description_chars": len(description),
            "content_chars": len(content),
        }
        await base.audit(self.session, actor, "skill.created", skill.id, details)
        return skill

    async def update(
        self,
        actor: Actor,
        skill_id: uuid.UUID,
        change: SkillChange,
        author: Principal | None = None,
    ) -> Skill:
        """`author` of a new version defaults to the actor (an accepted proposal names
        its agent, `proposals.py`)."""
        skill = await self.managed(actor, skill_id, change.version)
        details: dict[str, object] = {"changes": {}}
        if change.name is not None:
            name = base.name(change.name)
            if name != skill.name:
                skills = base.repo(self.session, actor)
                await base.unique_name(skills, skill.space_id, name, skill.id)
                details["changes"] = {"name": {"from": skill.name, "to": name}}
                skill.name = name
        texts = False
        if change.description is not None:
            description = base.description(change.description)
            if description != skill.description:
                skill.description, texts = description, True
                details["description_chars"] = len(description)
        if change.content is not None:
            content = base.content(change.content)
            if content != skill.content:
                skill.content, texts = content, True
                details["content_chars"] = len(content)
        if texts:
            who = author or actor.principal
            made = await base.repo(self.session, actor).add_version(skill, who)
            details["version_number"] = made.number
        skill.version += 1
        await self.session.flush()
        await base.audit(self.session, actor, "skill.updated", skill.id, details)
        return skill

    async def archive(self, actor: Actor, skill_id: uuid.UUID, version: int) -> Skill:
        return await self._state(actor, skill_id, version, SkillState.ARCHIVED)

    async def unarchive(self, actor: Actor, skill_id: uuid.UUID, version: int) -> Skill:
        return await self._state(actor, skill_id, version, SkillState.ACTIVE)

    async def managed(self, actor: Actor, skill_id: uuid.UUID, version: int) -> Skill:
        return await base.managed(self.session, actor, skill_id, version)

    async def authors(
        self, actor: Actor, rows: Sequence[Skill | SkillVersion]
    ) -> dict[Principal, str]:
        """Display names of the authors of skills or versions."""
        wanted = {Principal(PrincipalType(r.author_type), r.author_id) for r in rows}
        return await base.repo(self.session, actor).names(wanted)

    async def _state(
        self, actor: Actor, skill_id: uuid.UUID, version: int, state: SkillState
    ) -> Skill:
        skill = await self.managed(actor, skill_id, version)
        if skill.state == state:
            raise Conflict(code="skill.state_conflict", details={"state": skill.state})
        skill.state = state
        skill.version += 1
        await self.session.flush()
        action = "skill.archived" if state == SkillState.ARCHIVED else "skill.unarchived"
        await base.audit(self.session, actor, action, skill.id, {"name": skill.name})
        return skill
