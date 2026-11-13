"""Full-text search (spec 11, full text only in M2) over what the actor may see.

Visibility is decided in SQL by the same rules as everywhere else (`core/access.py`):
spaces the actor may read, drafts only where it holds `page.edit`. A space filter
the actor may not read is 404 `space.not_found`, as for an unknown id. Empty input
is an empty result, not an error.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require, space_ids_with, visible_space_ids
from app.core.pagination import PageParams, decode_score_cursor, encode_score_cursor
from app.modules.search.repository import SearchRepository, SearchScope
from app.modules.tags.models import SubjectType
from app.modules.tags.repository import tag_repository

HitType = Literal["page"]  # tickets and more join in later milestones
MAX_QUERY_CHARS = 1000


@dataclass(frozen=True, slots=True)
class SearchHit:
    """`snippet`: plain text with the matches between `⟦` and `⟧`."""

    type: HitType
    id: uuid.UUID
    space_id: uuid.UUID
    space_name: str
    title: str
    path: str
    snippet: str
    score: float


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        actor: Actor,
        q: str,
        *,
        space_id: uuid.UUID | None = None,
        tag_ids: Iterable[uuid.UUID] | None = None,
        types: Sequence[HitType] = ("page",),
        params: PageParams,
    ) -> pagination.Page[SearchHit]:
        """Best first. With `space_id`, only that space; with `tag_ids`, only what
        carries every one of the tags."""
        after = decode_score_cursor(params.cursor) if params.cursor else None
        if space_id is not None:
            await require(self.session, actor, Action.SPACE_READ, space_id)
        q = q.strip()[:MAX_QUERY_CHARS]
        if not q or "page" not in types:
            return pagination.Page[SearchHit](items=[])
        tags = tag_repository(self.session, actor)
        among = [tags.subject_ids(SubjectType.PAGE, [t]) for t in dict.fromkeys(tag_ids or ())]
        scope = SearchScope(
            actor.org_id, visible_space_ids(actor), space_ids_with(actor, Action.PAGE_EDIT)
        )
        rows = await SearchRepository(self.session, scope).pages(
            q, space_id=space_id, among=among, after=after, limit=params.limit + 1
        )
        items = [
            SearchHit(
                "page", r.page_id, r.space_id, r.space_name, r.title, r.path, r.snippet, r.score
            )
            for r in rows[: params.limit]
        ]
        more = len(rows) > params.limit
        cursor = encode_score_cursor(items[-1].score, items[-1].id) if more else None
        return pagination.Page[SearchHit](items=items, next_cursor=cursor)
