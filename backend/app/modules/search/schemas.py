import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.pagination import Page
from app.core.principal import PrincipalType
from app.modules.messaging.models import ConversationKind
from app.modules.messaging.search import MessageHit
from app.modules.search.service import SearchHit


class PageHitOut(BaseModel):
    """A page. `snippet` is plain text: render it as text and highlight what stands
    between `⟦` and `⟧`. `score` orders the hits (higher is better); it has no unit."""

    type: Literal["page"]
    id: uuid.UUID
    space_id: uuid.UUID
    space_name: str
    title: str
    path: str
    snippet: str
    score: float

    @classmethod
    def of(cls, hit: SearchHit) -> "PageHitOut":
        return cls(
            type="page",
            id=hit.id,
            space_id=hit.space_id,
            space_name=hit.space_name,
            title=hit.title,
            path=hit.path,
            snippet=hit.snippet,
            score=hit.score,
        )


class HitConversation(BaseModel):
    """Where a message stands. `name`: a channel's (null otherwise); `page_id`: a page
    thread's page (null otherwise); `space_id`: null for a direct message."""

    id: uuid.UUID
    kind: ConversationKind
    name: str | None
    space_id: uuid.UUID | None
    page_id: uuid.UUID | None


class HitAuthor(BaseModel):
    type: PrincipalType
    id: uuid.UUID
    name: str


class MessageHitOut(BaseModel):
    """A message (`id`); `parent_id`: the thread it is a reply in (null: top level).
    `snippet` and `score` as for pages."""

    type: Literal["message"]
    id: uuid.UUID
    parent_id: uuid.UUID | None
    conversation: HitConversation
    author: HitAuthor | None
    created_at: datetime
    snippet: str
    score: float

    @classmethod
    def of(cls, hit: MessageHit) -> "MessageHitOut":
        author = None
        if hit.author_id is not None and hit.author_name is not None:
            author = HitAuthor(type=PrincipalType.USER, id=hit.author_id, name=hit.author_name)
        return cls(
            type="message",
            id=hit.message_id,
            parent_id=hit.parent_id,
            conversation=HitConversation(
                id=hit.conversation_id,
                kind=hit.conversation_kind,
                name=hit.conversation_name,
                space_id=hit.space_id,
                page_id=hit.page_id,
            ),
            author=author,
            created_at=hit.created_at,
            snippet=hit.snippet,
            score=hit.score,
        )


SearchHitOut = Annotated[PageHitOut | MessageHitOut, Field(discriminator="type")]


class SearchResults(Page[SearchHitOut]):
    """A page of hits of both kinds, told apart by `type`."""


def hit_out(hit: SearchHit | MessageHit) -> PageHitOut | MessageHitOut:
    return PageHitOut.of(hit) if isinstance(hit, SearchHit) else MessageHitOut.of(hit)
