"""Skill import and export. An import is the SKILL.md or ZIP as the raw request body,
at most `MAX_IMPORT_BYTES` (`web/public.body_limits`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.downloads import content_disposition
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.auth.write_limits import UPLOAD
from app.modules.skills.format import FILENAME
from app.modules.skills.transfer import ImportResult, SkillTransfer

skill_transfer = APIRouter(prefix="/skills", tags=["skills"])

_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/zip": {"schema": {"type": "string", "format": "binary"}},
            "text/markdown": {"schema": {"type": "string"}},
        },
    }
}
_DOWNLOAD = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-cache"}


class SkillImportCreatedOut(BaseModel):
    """`ignored_fields`: optional front matter fields of the format that are not kept."""

    path: str
    skill_id: uuid.UUID
    name: str
    ignored_fields: list[str]


class SkillImportSkippedOut(BaseModel):
    """`path`: the entry's name in the archive (`SKILL.md` for a single file).
    `reason`: unsafe_path, not_in_skill, file_unsupported (a skill is its SKILL.md
    only), too_deep, too_many, too_large, unreadable, invalid_text,
    frontmatter_invalid, name_invalid, description_invalid, content_invalid,
    name_mismatch (name and folder differ), duplicate (twice in the import), exists
    (the scope has a skill of that name)."""

    path: str
    reason: str


class SkillImportOut(BaseModel):
    created: list[SkillImportCreatedOut]
    skipped: list[SkillImportSkippedOut]

    @classmethod
    def of(cls, result: ImportResult) -> "SkillImportOut":
        return cls(
            created=[
                SkillImportCreatedOut(
                    path=c.path, skill_id=c.skill_id, name=c.name, ignored_fields=c.ignored_fields
                )
                for c in result.created
            ],
            skipped=[SkillImportSkippedOut(path=s.path, reason=s.reason) for s in result.skipped],
        )


@skill_transfer.post(
    "/import", response_model=SkillImportOut, openapi_extra=_BODY, dependencies=UPLOAD
)
async def import_skills(
    request: Request,
    actor: ActorDep,
    session: SessionDep,
    space_id: Annotated[uuid.UUID | None, Query(description="none: organisation-wide")] = None,
) -> SkillImportOut:
    """Skills from a SKILL.md or a ZIP of skill folders (`skill.manage`, or
    `page.moderate` in the space); 413 `import.too_large` over 10 MB or the archive's
    limits, 422 `import.invalid_zip` for a broken ZIP. Each skill is reported."""
    result = await SkillTransfer(session).import_body(actor, space_id, request.stream())
    return SkillImportOut.of(result)


@skill_transfer.get(
    "/{skill_id}/export",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}}}},
)
async def export_skill(skill_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> Response:
    """The skill's SKILL.md."""
    text = await SkillTransfer(session).export(actor, skill_id)
    headers = {**_DOWNLOAD, "Content-Disposition": content_disposition("attachment", FILENAME)}
    return Response(text, media_type="text/markdown; charset=utf-8", headers=headers)
