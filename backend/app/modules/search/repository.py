"""The SQL of the search. Rights are part of the one statement (spec 11): the actor's
organisation, the spaces it may read, pages outside the trash, and drafts only in the
spaces where it may edit pages. Nothing outside that set is ranked, counted or quoted.

A page matches when the query matches its `search_tsv` (German stems or words as
written), or, for short input, when its title starts with the input. The score is the
cover-density rank plus 1 for a title that starts with the input; ties go by id.
Snippets come from `ts_headline` for the returned rows only.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import (
    ColumnElement,
    Float,
    Select,
    and_,
    case,
    cast,
    false,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spaces.models import Space
from app.modules.wiki.models import Page
from app.modules.wiki.repository import page_seen

START, STOP = "⟦", "⟧"  # the client highlights between them; no HTML
_HEADLINE = (
    f"StartSel={START}, StopSel={STOP}, MaxWords=30, MinWords=12, "
    'MaxFragments=2, FragmentDelimiter=" … "'
)
_GERMAN = cast(literal("german"), REGCONFIG)
_SIMPLE = cast(literal("simple"), REGCONFIG)
PREFIX_MAX_CHARS = 50  # longer input is not matched as a title prefix


@dataclass(frozen=True, slots=True)
class SearchScope:
    org_id: uuid.UUID
    readable: Select[uuid.UUID]  # spaces the actor may read (SQL)
    drafts: Select[uuid.UUID]  # spaces where it may see drafts (SQL)
    ai: bool = False  # for an agent's tool: pages locked for AI (`no_ai`) left out


@dataclass(frozen=True, slots=True)
class PageHit:
    page_id: uuid.UUID
    space_id: uuid.UUID
    space_name: str
    title: str
    path: str
    snippet: str
    score: float


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def title_starts_with(q: str) -> ColumnElement[bool]:
    """Case-insensitive title prefix, in the form `ix_page_title_prefix` serves
    (`lower(title) text_pattern_ops`, review M2 R19)."""
    pattern = func.lower(literal(f"{_escape_like(q)}%"))
    return func.lower(Page.title).like(pattern, escape="\\")


class SearchRepository:
    def __init__(self, session: AsyncSession, scope: SearchScope) -> None:
        self.session = session
        self.scope = scope

    def _allowed(self) -> ColumnElement[bool]:
        seen = page_seen(self.scope.org_id, self.scope.readable, self.scope.drafts)
        return and_(seen, Page.no_ai.is_(false())) if self.scope.ai else seen

    async def pages(
        self,
        q: str,
        *,
        space_id: uuid.UUID | None,
        among: list[Select[uuid.UUID]],
        after: tuple[float, uuid.UUID] | None,
        limit: int,
    ) -> list[PageHit]:
        """Best first; `among` narrows to pages each of the selects contains."""
        query = func.websearch_to_tsquery(_GERMAN, q).op("||")(
            func.websearch_to_tsquery(_SIMPLE, q)
        )
        matches: ColumnElement[bool] = Page.search_tsv.op("@@")(query)
        score: ColumnElement[float] = cast(func.ts_rank_cd(Page.search_tsv, query), Float)
        if len(q) <= PREFIX_MAX_CHARS:
            prefix = title_starts_with(q)
            matches = or_(matches, prefix)
            score = score + case((prefix, 1.0), else_=0.0)
        ranked = select(Page.id.label("id"), score.label("score")).where(self._allowed(), matches)
        if space_id is not None:
            ranked = ranked.where(Page.space_id == space_id)
        for ids in among:
            ranked = ranked.where(Page.id.in_(ids))
        inner = ranked.subquery()
        best = select(inner.c.id, inner.c.score)
        if after is not None:
            best = best.where(
                or_(
                    inner.c.score < after[0],
                    and_(inner.c.score == after[0], inner.c.id > after[1]),
                )
            )
        top = best.order_by(inner.c.score.desc(), inner.c.id).limit(limit).subquery()
        snippet = func.ts_headline(_GERMAN, Page.content_md, query, _HEADLINE)
        stmt = (
            select(Page.id, Page.space_id, Space.name, Page.title, Page.path, snippet, top.c.score)
            .join(top, top.c.id == Page.id)
            .join(Space, Space.id == Page.space_id)
            .order_by(top.c.score.desc(), Page.id)
        )
        rows = (await self.session.execute(stmt)).all()
        return [PageHit(*row) for row in rows]
