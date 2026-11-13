"""The SQL of the search in messages (plan M3 task 9), for `search.py`.

Rights are part of the one statement, for every kind of conversation at once:
`visible_conversations` (channels through the spaces the actor may read, direct
messages through taking part, page threads through the page's visibility, ticket
threads through the ticket's space). An admin's
inspection of a DM gives no access here. Deleted and system messages are never
matched (`message.search_tsv`, partial index). Ranked like page content (German
stems or words as written, cover density); ties by id; snippets only for the
returned rows.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    ColumnElement,
    Float,
    and_,
    cast,
    func,
    literal,
    literal_column,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.models import Conversation, ConversationKind, Message, MessageKind
from app.modules.messaging.repository import ConversationScope, visible_conversations
from app.modules.tickets.models import WorkItem
from app.modules.users.models import User

START, STOP = "⟦", "⟧"
_HEADLINE = (
    f"StartSel={START}, StopSel={STOP}, MaxWords=30, MinWords=12, "
    'MaxFragments=2, FragmentDelimiter=" … "'
)
_GERMAN = cast(literal("german"), REGCONFIG)
_SIMPLE = cast(literal("simple"), REGCONFIG)


@dataclass(frozen=True, slots=True)
class MessageHit:
    message_id: uuid.UUID
    parent_id: uuid.UUID | None
    conversation_id: uuid.UUID
    conversation_kind: ConversationKind
    conversation_name: str | None
    space_id: uuid.UUID | None
    page_id: uuid.UUID | None
    ticket_number: int | None
    author_id: uuid.UUID | None
    author_name: str | None
    created_at: datetime
    snippet: str
    score: float


def searchable() -> ColumnElement[bool]:
    """The messages the search index holds (`ix_message_search_tsv`'s predicate, as
    literals, so every plan can use the partial index)."""
    return and_(
        Message.kind == literal_column(f"'{MessageKind.HUMAN.value}'"),
        Message.deleted_at.is_(None),
    )


class MessageSearchRepository:
    def __init__(self, session: AsyncSession, scope: ConversationScope) -> None:
        self.session = session
        self.scope = scope

    async def messages(
        self,
        q: str,
        *,
        space_id: uuid.UUID | None,
        after: tuple[float, uuid.UUID] | None,
        limit: int,
    ) -> list[MessageHit]:
        """Best first; with `space_id`, only conversations of that space."""
        query = func.websearch_to_tsquery(_GERMAN, q).op("||")(
            func.websearch_to_tsquery(_SIMPLE, q)
        )
        score: ColumnElement[float] = cast(func.ts_rank_cd(Message.search_tsv, query), Float)
        seen = select(Conversation.id).where(visible_conversations(self.scope))
        if space_id is not None:
            seen = seen.where(Conversation.space_id == space_id)
        ranked = select(Message.id.label("id"), score.label("score")).where(
            Message.org_id == self.scope.org_id,
            searchable(),
            Message.search_tsv.op("@@")(query),
            Message.conversation_id.in_(seen),
        )
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
        snippet = func.ts_headline(_GERMAN, Message.body_md, query, _HEADLINE)
        stmt = (
            select(
                Message.id,
                Message.parent_id,
                Conversation.id,
                Conversation.kind,
                Conversation.name,
                Conversation.space_id,
                Conversation.page_id,
                WorkItem.number,
                Message.author_id,
                User.name,
                Message.created_at,
                snippet,
                top.c.score,
            )
            .join(top, top.c.id == Message.id)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .outerjoin(WorkItem, WorkItem.id == Conversation.work_item_id)
            .outerjoin(User, User.id == Message.author_id)
            .order_by(top.c.score.desc(), Message.id)
        )
        rows = (await self.session.execute(stmt)).all()
        return [MessageHit(*tuple(row)) for row in rows]
