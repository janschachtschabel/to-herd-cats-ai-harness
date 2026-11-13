import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.search.schemas import SearchHitOut
from app.modules.search.service import MAX_QUERY_CHARS, SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=Page[SearchHitOut])
async def search(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    q: Annotated[str, Query(max_length=MAX_QUERY_CHARS)] = "",
    space_id: Annotated[uuid.UUID | None, Query(description="only this space")] = None,
    tag: Annotated[list[uuid.UUID] | None, Query(description="only with every tag")] = None,
) -> Page[SearchHitOut]:
    """Pages the caller may see, best first; empty `q` gives an empty list."""
    page = await SearchService(session).search(
        actor, q, space_id=space_id, tag_ids=tag, params=params
    )
    return Page[SearchHitOut](
        items=[SearchHitOut.of(h) for h in page.items], next_cursor=page.next_cursor
    )
