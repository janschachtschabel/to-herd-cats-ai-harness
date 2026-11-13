import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.principal import PrincipalType
from app.modules.messaging.activity_repository import ActivityEntry
from app.modules.messaging.models import ConversationKind
from app.modules.messaging.notification_models import NotificationReason


class ActivityConversation(BaseModel):
    """`name` is null for a direct message and a page or ticket thread; `page_id` names
    a page thread's page, `ticket_number` a ticket thread's ticket (null for other
    kinds; the ticket's address is `/tickets/<number>`)."""

    id: uuid.UUID
    kind: ConversationKind
    name: str | None
    space_id: uuid.UUID | None
    page_id: uuid.UUID | None
    ticket_number: int | None


class ActivityAuthor(BaseModel):
    type: PrincipalType
    id: uuid.UUID
    name: str


class ActivityOut(BaseModel):
    """A notification: why, where, from whom, and the first 140 characters of the
    message's Markdown. `parent_id`: the thread the message is in (null: top level).
    `read_at`/`done_at`: null until marked. An `assignment` points at a timeline entry:
    `author` is who assigned, `snippet` is empty."""

    id: uuid.UUID
    reason: NotificationReason
    created_at: datetime
    read_at: datetime | None
    done_at: datetime | None
    conversation: ActivityConversation
    message_id: uuid.UUID
    parent_id: uuid.UUID | None
    author: ActivityAuthor | None
    snippet: str

    @classmethod
    def of(cls, entry: ActivityEntry) -> "ActivityOut":
        n = entry.notification
        author = None
        if entry.author_id is not None and entry.author_name is not None:
            author = ActivityAuthor(
                type=PrincipalType.USER, id=entry.author_id, name=entry.author_name
            )
        return cls(
            id=n.id,
            reason=n.reason,
            created_at=n.created_at,
            read_at=n.read_at,
            done_at=n.done_at,
            conversation=ActivityConversation(
                id=n.conversation_id,
                kind=entry.conversation_kind,
                name=entry.conversation_name,
                space_id=entry.space_id,
                page_id=entry.page_id,
                ticket_number=entry.ticket_number,
            ),
            message_id=n.message_id,
            parent_id=entry.parent_id,
            author=author,
            snippet=entry.snippet,
        )


class ActivityCountOut(BaseModel):
    """`open`: not done; `unread`: not done and not read (the badge)."""

    open: int
    unread: int
