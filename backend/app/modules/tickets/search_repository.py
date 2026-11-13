"""The SQL of the search in tickets (plan M4 task 4, spec 11), for `search.py`.

Rights are part of the one statement: the actor's organisation and the spaces where it
may read tickets (`TicketScope`). A ticket matches when the query matches its
`search_tsv` (title stemmed and as written, then the description), or when the input
is a key (`HC-42`, `42`) of its number; that hit is ranked first (`KEY_SCORE` on top
of the text rank). Ties go by id; snippets come from the description, for the returned
rows only.
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

from app.modules.spaces.models import Space
from app.modules.tickets.models import TicketKind, TicketStatus, WorkItem
from app.modules.tickets.repository import TicketRepository

START, STOP = "⟦", "⟧"  # the client highlights between them; no HTML
_HEADLINE = (
    f"StartSel={START}, StopSel={STOP}, MaxWords=30, MinWords=12, "
    'MaxFragments=2, FragmentDelimiter=" … "'
)
_GERMAN = cast(literal("german"), REGCONFIG)
_SIMPLE = cast(literal("simple"), REGCONFIG)
KEY_SCORE = 100.0  # a key's own ticket comes before any text match


@dataclass(frozen=True, slots=True)
class TicketHit:
    id: uuid.UUID
    number: int
    title: str
    kind: TicketKind
    status: TicketStatus
    space_id: uuid.UUID
    space_name: str
    snippet: str
    score: float


class TicketSearchRepository(TicketRepository):
    async def hits(
        self,
        q: str,
        *,
        number: int | None,
        space_id: uuid.UUID | None,
        among: list[Select[uuid.UUID]],
        after: tuple[float, uuid.UUID] | None,
        limit: int,
    ) -> list[TicketHit]:
        """Best first, below `after` (score, id); `number`: the ticket the input names
        as a key; `among` narrows to tickets each of the selects contains."""
        query = func.websearch_to_tsquery(_GERMAN, q).op("||")(
            func.websearch_to_tsquery(_SIMPLE, q)
        )
        matches: ColumnElement[bool] = WorkItem.search_tsv.op("@@")(query)
        score: ColumnElement[float] = cast(func.ts_rank_cd(WorkItem.search_tsv, query), Float)
        keyed: ColumnElement[bool] = false() if number is None else WorkItem.number == number
        matches = or_(matches, keyed)
        score = score + case((keyed, KEY_SCORE), else_=0.0)
        ranked = select(WorkItem.id.label("id"), score.label("score")).where(
            self._visible(), matches
        )
        if space_id is not None:
            ranked = ranked.where(WorkItem.space_id == space_id)
        for ids in among:
            ranked = ranked.where(WorkItem.id.in_(ids))
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
        snippet = func.ts_headline(_GERMAN, WorkItem.description_md, query, _HEADLINE)
        stmt = (
            select(
                WorkItem.id,
                WorkItem.number,
                WorkItem.title,
                WorkItem.kind,
                TicketStatus,
                WorkItem.space_id,
                Space.name,
                snippet,
                top.c.score,
            )
            .join(top, top.c.id == WorkItem.id)
            .join(TicketStatus, TicketStatus.id == WorkItem.status_id)
            .join(Space, Space.id == WorkItem.space_id)
            .order_by(top.c.score.desc(), WorkItem.id)
        )
        rows = (await self.session.execute(stmt)).all()
        return [TicketHit(*tuple(row)) for row in rows]
