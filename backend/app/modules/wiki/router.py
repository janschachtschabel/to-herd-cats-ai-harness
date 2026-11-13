import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.wiki.schemas import (
    ExpectedVersion,
    PageCreate,
    PageMove,
    PageOut,
    PageUpdate,
    TrashedPageOut,
    TreeNodeOut,
)
from app.modules.wiki.service import PageService

space_pages = APIRouter(prefix="/spaces/{space_id}/pages", tags=["wiki"])
space_trash = APIRouter(prefix="/spaces/{space_id}/trash", tags=["wiki"])
pages = APIRouter(prefix="/pages", tags=["wiki"])

PathQuery = Annotated[str, Query(min_length=1, max_length=2000, description="e.g. `it/zugaenge`")]


@space_pages.get("/tree", response_model=Page[TreeNodeOut])
async def page_tree(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[TreeNodeOut]:
    page = await PageService(session).tree(actor, space_id, params)
    return Page[TreeNodeOut](
        items=[TreeNodeOut.of(p) for p in page.items], next_cursor=page.next_cursor
    )


@space_pages.post("", response_model=PageOut, status_code=201)
async def create_page(
    space_id: uuid.UUID, body: PageCreate, actor: ActorDep, session: SessionDep
) -> PageOut:
    page = await PageService(session).create(
        actor, space_id, body.parent_id, body.title, body.content_md
    )
    return PageOut.of(page)


@space_pages.get("/by-path", response_model=PageOut)
async def page_by_path(
    space_id: uuid.UUID, path: PathQuery, actor: ActorDep, session: SessionDep
) -> PageOut:
    return PageOut.of(await PageService(session).get_by_path(actor, space_id, path))


@pages.get("/{page_id}", response_model=PageOut)
async def get_page(page_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> PageOut:
    return PageOut.of(await PageService(session).get(actor, page_id))


@pages.patch("/{page_id}", response_model=PageOut)
async def update_page(
    page_id: uuid.UUID, body: PageUpdate, actor: ActorDep, session: SessionDep
) -> PageOut:
    page = await PageService(session).update(
        actor, page_id, title=body.title, content_md=body.content_md, version=body.version
    )
    return PageOut.of(page)


@pages.post("/{page_id}/publish", response_model=PageOut)
async def publish_page(
    page_id: uuid.UUID, body: ExpectedVersion, actor: ActorDep, session: SessionDep
) -> PageOut:
    return PageOut.of(await PageService(session).publish(actor, page_id, body.version))


@pages.post("/{page_id}/move", response_model=PageOut)
async def move_page(
    page_id: uuid.UUID, body: PageMove, actor: ActorDep, session: SessionDep
) -> PageOut:
    page = await PageService(session).move(
        actor, page_id, new_parent_id=body.parent_id, position=body.position, version=body.version
    )
    return PageOut.of(page)


@pages.post("/{page_id}/trash", status_code=204)
async def trash_page(
    page_id: uuid.UUID, body: ExpectedVersion, actor: ActorDep, session: SessionDep
) -> None:
    await PageService(session).trash(actor, page_id, body.version)


@pages.post("/{page_id}/restore", response_model=PageOut)
async def restore_page(page_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> PageOut:
    return PageOut.of(await PageService(session).restore_from_trash(actor, page_id))


@pages.delete("/{page_id}", status_code=204)
async def purge_page(page_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    """Delete a page in the trash for good, with everything below it (system admins)."""
    await PageService(session).purge(actor, page_id)


@space_trash.get("", response_model=Page[TrashedPageOut])
async def list_trash(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[TrashedPageOut]:
    page = await PageService(session).list_trash(actor, space_id, params)
    return Page[TrashedPageOut](
        items=[TrashedPageOut.of(p) for p in page.items], next_cursor=page.next_cursor
    )
