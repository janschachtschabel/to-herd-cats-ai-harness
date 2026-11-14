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


class ActivityProposal(BaseModel):
    """The proposal a notification is about when it has no thread to point at (a new
    page at the top level; its address: the space's proposals)."""

    id: uuid.UUID
    space_id: uuid.UUID


class ActivitySkillProposal(BaseModel):
    """The skill proposal a notification is about (a skill has no thread; its address:
    `/api/skill-proposals/{id}`); `space_id` none: organisation-wide."""

    id: uuid.UUID
    space_id: uuid.UUID | None


class ActivityOut(BaseModel):
    """A notification: why, where, from whom, and the first 140 characters of the
    message's Markdown. `parent_id`: the thread the message is in (null: top level).
    `read_at`/`done_at`: null until marked. An `assignment` points at a timeline entry:
    `author` is who assigned, `snippet` is empty. A `proposal` for a new page at the top
    level has no conversation and no message, but `proposal` (plan M6); a
    `skill_proposal` has `skill_proposal` instead (plan M6 task 9); `author` may be an
    agent (`type`)."""

    id: uuid.UUID
    reason: NotificationReason
    created_at: datetime
    read_at: datetime | None
    done_at: datetime | None
    conversation: ActivityConversation | None
    message_id: uuid.UUID | None
    proposal: ActivityProposal | None = None
    skill_proposal: ActivitySkillProposal | None = None
    parent_id: uuid.UUID | None
    author: ActivityAuthor | None
    snippet: str

    @classmethod
    def of(cls, entry: ActivityEntry) -> "ActivityOut":
        n = entry.notification
        author = None
        if entry.author_id is not None and entry.author_name is not None:
            kind = PrincipalType(entry.author_type or PrincipalType.USER)
            author = ActivityAuthor(type=kind, id=entry.author_id, name=entry.author_name)
        conversation = None
        if n.conversation_id is not None and entry.conversation_kind is not None:
            conversation = ActivityConversation(
                id=n.conversation_id,
                kind=entry.conversation_kind,
                name=entry.conversation_name,
                space_id=entry.space_id,
                page_id=entry.page_id,
                ticket_number=entry.ticket_number,
            )
        proposal = None
        if n.proposal_id is not None and n.space_id is not None:
            proposal = ActivityProposal(id=n.proposal_id, space_id=n.space_id)
        skill_proposal = None
        if n.skill_proposal_id is not None:
            skill_proposal = ActivitySkillProposal(id=n.skill_proposal_id, space_id=n.space_id)
        return cls(
            id=n.id,
            reason=n.reason,
            created_at=n.created_at,
            read_at=n.read_at,
            done_at=n.done_at,
            conversation=conversation,
            proposal=proposal,
            skill_proposal=skill_proposal,
            message_id=n.message_id,
            parent_id=entry.parent_id,
            author=author,
            snippet=entry.snippet,
        )


class ActivityCountOut(BaseModel):
    """`open`: not done; `unread`: not done and not read (the badge)."""

    open: int
    unread: int
