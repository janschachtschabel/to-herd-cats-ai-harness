from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.directory.schemas import DirectoryEntryOut, DirectoryQuery
from app.modules.directory.service import DirectoryService

router = APIRouter(prefix="/directory", tags=["directory"])


@router.get("", response_model=Page[DirectoryEntryOut])
async def search_directory(
    query: Annotated[DirectoryQuery, Query()], actor: ActorDep, session: SessionDep
) -> Page[DirectoryEntryOut]:
    page = await DirectoryService(session).search(actor, query)
    return Page[DirectoryEntryOut](
        items=[DirectoryEntryOut.of(e) for e in page.items], next_cursor=page.next_cursor
    )
