"""Skill routes. Without `ai.use` or `skill.manage` every one answers 404
`skill.not_found`, as for an unknown id; a skill of a space one cannot read too.
Import and export: `transfer_router.py`; an agent's skills: `assignment_router.py`."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.errors import ValidationFailed
from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.skills.models import Skill, SkillState
from app.modules.skills.repository import SkillFilter
from app.modules.skills.schemas import (
    SkillCreate,
    SkillDetailOut,
    SkillOut,
    SkillUpdate,
    SkillVersionDetailOut,
    SkillVersionIn,
    SkillVersionOut,
)
from app.modules.skills.service import SkillChange, SkillDraft, SkillService
from app.modules.skills.versions import SkillVersions

skills = APIRouter(prefix="/skills", tags=["skills"])


async def _detail(service: SkillService, actor: ActorDep, skill: Skill) -> SkillDetailOut:
    return SkillDetailOut.of(skill, await service.authors(actor, [skill]))


@skills.get("", response_model=Page[SkillOut])
async def list_skills(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    space_id: Annotated[uuid.UUID | None, Query(description="only this space's")] = None,
    org_wide: Annotated[
        bool | None, Query(description="true: only organisation-wide; false: only spaces'")
    ] = None,
    state: Annotated[SkillState | None, Query(description="only this state")] = None,
    q: Annotated[str | None, Query(description="a part of the name", max_length=64)] = None,
) -> Page[SkillOut]:
    """By name: organisation-wide skills and those of the spaces the caller reads."""
    service = SkillService(session)
    where = SkillFilter(space_id=space_id, org_wide=org_wide, state=state, query=q or None)
    page = await service.list(actor, where, params)
    names = await service.authors(actor, page.items)
    return Page[SkillOut](
        items=[SkillOut.of(s, names) for s in page.items], next_cursor=page.next_cursor
    )


@skills.post("", response_model=SkillDetailOut, status_code=201)
async def create_skill(body: SkillCreate, actor: ActorDep, session: SessionDep) -> SkillDetailOut:
    """Organisation-wide: `skill.manage`; in a space: `page.moderate` there. 409
    `skill.name_taken` when the scope has a skill of that name (archived included)."""
    service = SkillService(session)
    draft = SkillDraft(body.name, body.description, body.content, body.space_id)
    return await _detail(service, actor, await service.create(actor, draft))


@skills.get("/{skill_id}", response_model=SkillDetailOut)
async def get_skill(skill_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> SkillDetailOut:
    service = SkillService(session)
    return await _detail(service, actor, await service.get(actor, skill_id))


@skills.patch("/{skill_id}", response_model=SkillDetailOut)
async def update_skill(
    skill_id: uuid.UUID, body: SkillUpdate, actor: ActorDep, session: SessionDep
) -> SkillDetailOut:
    """A change of description or content makes a new version."""
    for field in body.model_fields_set - {"version"}:
        if getattr(body, field) is None:
            raise ValidationFailed(f"{field} cannot be null", code="validation_failed")
    service = SkillService(session)
    change = SkillChange(body.version, body.name, body.description, body.content)
    return await _detail(service, actor, await service.update(actor, skill_id, change))


@skills.post("/{skill_id}/archive", response_model=SkillDetailOut)
async def archive_skill(
    skill_id: uuid.UUID, body: SkillVersionIn, actor: ActorDep, session: SessionDep
) -> SkillDetailOut:
    """No run uses an archived skill; 409 `skill.state_conflict` if it is archived."""
    service = SkillService(session)
    return await _detail(service, actor, await service.archive(actor, skill_id, body.version))


@skills.post("/{skill_id}/unarchive", response_model=SkillDetailOut)
async def unarchive_skill(
    skill_id: uuid.UUID, body: SkillVersionIn, actor: ActorDep, session: SessionDep
) -> SkillDetailOut:
    service = SkillService(session)
    return await _detail(service, actor, await service.unarchive(actor, skill_id, body.version))


@skills.get("/{skill_id}/versions", response_model=Page[SkillVersionOut])
async def list_skill_versions(
    skill_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[SkillVersionOut]:
    """Newest first, without their text."""
    page = await SkillVersions(session).list(actor, skill_id, params)
    names = await SkillService(session).authors(actor, page.items)
    return Page[SkillVersionOut](
        items=[SkillVersionOut.of(v, names) for v in page.items], next_cursor=page.next_cursor
    )


@skills.get("/{skill_id}/versions/{number}", response_model=SkillVersionDetailOut)
async def get_skill_version(
    skill_id: uuid.UUID, number: int, actor: ActorDep, session: SessionDep
) -> SkillVersionDetailOut:
    version = await SkillVersions(session).get(actor, skill_id, number)
    names = await SkillService(session).authors(actor, [version])
    return SkillVersionDetailOut.of(version, names)


@skills.post("/{skill_id}/versions/{number}/restore", response_model=SkillDetailOut)
async def restore_skill_version(
    skill_id: uuid.UUID, number: int, body: SkillVersionIn, actor: ActorDep, session: SessionDep
) -> SkillDetailOut:
    """A new version with that version's description and content."""
    skill = await SkillVersions(session).restore(actor, skill_id, number, body.version)
    return await _detail(SkillService(session), actor, skill)
