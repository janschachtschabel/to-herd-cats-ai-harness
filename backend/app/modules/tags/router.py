import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.tags.schemas import TagCreate, TagOut, TagUpdate
from app.modules.tags.service import TagService

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=Page[TagOut])
async def list_tags(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    space_id: Annotated[
        uuid.UUID | None, Query(description="only system-wide tags and this space's")
    ] = None,
    system: Annotated[
        bool, Query(description="only system-wide tags; not together with space_id")
    ] = False,
) -> Page[TagOut]:
    page = await TagService(session).list(actor, params, space_id, system_only=system)
    return Page[TagOut](items=[TagOut.of(t) for t in page.items], next_cursor=page.next_cursor)


@router.post("", response_model=TagOut, status_code=201)
async def create_tag(body: TagCreate, actor: ActorDep, session: SessionDep) -> TagOut:
    tag = await TagService(session).create(actor, body.name, body.color, body.space_id)
    return TagOut.of(tag)


@router.patch("/{tag_id}", response_model=TagOut)
async def update_tag(
    tag_id: uuid.UUID, body: TagUpdate, actor: ActorDep, session: SessionDep
) -> TagOut:
    tag = await TagService(session).update(
        actor, tag_id, name=body.name, color=body.color, version=body.version
    )
    return TagOut.of(tag)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(tag_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    """Also takes the tag off everything that carries it."""
    await TagService(session).delete(actor, tag_id)
