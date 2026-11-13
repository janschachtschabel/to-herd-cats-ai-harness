import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Query

from app.core.errors import ValidationFailed
from app.core.pagination import PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.search.schemas import SearchResults, hit_out
from app.modules.search.service import HIT_TYPES, MAX_QUERY_CHARS, HitType, SearchService

router = APIRouter(prefix="/search", tags=["search"])


def _types(raw: str) -> list[HitType]:
    """`page,message` (any order, either alone); anything else is 422."""
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if not names or any(name not in HIT_TYPES for name in names):
        raise ValidationFailed(
            f"types: a comma-separated list of {', '.join(HIT_TYPES)}", code="search.bad_types"
        )
    return [cast(HitType, name) for name in names]


@router.get("", response_model=SearchResults)
async def search(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    q: Annotated[str, Query(max_length=MAX_QUERY_CHARS)] = "",
    space_id: Annotated[uuid.UUID | None, Query(description="only this space")] = None,
    tag: Annotated[list[uuid.UUID] | None, Query(description="only with every tag")] = None,
    types: Annotated[
        str, Query(max_length=100, description="what to find: page, message (comma-separated)")
    ] = ",".join(HIT_TYPES),
) -> SearchResults:
    """Pages and messages the caller may see, best first; empty `q` gives an empty
    list. Tags narrow to pages."""
    page = await SearchService(session).search(
        actor, q, space_id=space_id, tag_ids=tag, types=_types(types), params=params
    )
    return SearchResults(items=[hit_out(h) for h in page.items], next_cursor=page.next_cursor)
