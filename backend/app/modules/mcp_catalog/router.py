"""Catalogue routes (`ai.manage`; anyone else: 404 `ai.not_found`)."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.mcp_catalog.schemas import EntryOut, InstallIn, InstallOut, ProblemOut
from app.modules.mcp_catalog.service import CatalogService

router = APIRouter(prefix="/ai/mcp-catalog", tags=["mcp"])

EntryId = Annotated[str, Path(max_length=40)]


@router.get("", response_model=Page[EntryOut])
async def list_entries(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[EntryOut]:
    return await CatalogService(session).list(actor, params)


@router.get("/problems", response_model=Page[ProblemOut])
async def list_problems(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[ProblemOut]:
    """Files that could not be loaded and were skipped: which, and why."""
    page = await CatalogService(session).problems(actor, params)
    items = [ProblemOut.of(p) for p in page.items]
    return Page[ProblemOut](items=items, next_cursor=page.next_cursor)


@router.get("/{entry_id}", response_model=EntryOut)
async def get_entry(entry_id: EntryId, actor: ActorDep, session: SessionDep) -> EntryOut:
    return await CatalogService(session).get(actor, entry_id)


@router.post("/{entry_id}/install", response_model=InstallOut, status_code=201)
async def install_entry(
    entry_id: EntryId, body: InstallIn, actor: ActorDep, session: SessionDep
) -> InstallOut:
    """Create the server (and its OAuth client and shared connector, as the scope and
    kind need) from the entry; `server.refresh` says how reading its tools went."""
    return await CatalogService(session).install(actor, entry_id, body)
