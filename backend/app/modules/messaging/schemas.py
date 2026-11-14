"""The conversation shapes of the messaging API: channels, participants, a
conversation. Messages: `message_schemas.py`."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.principal import PrincipalType
from app.modules.messaging.dm_repository import InspectionNote, Participant
from app.modules.messaging.models import (
    MAX_CHANNEL_NAME_CHARS,
    MAX_TOPIC_CHARS,
    Conversation,
    ConversationKind,
)

# No line breaks or other control characters: a name is one line in the sidebar.
ChannelName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_CHANNEL_NAME_CHARS,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
Topic = Annotated[str, Field(max_length=MAX_TOPIC_CHARS)]


class PrincipalRef(BaseModel):
    type: PrincipalType
    id: uuid.UUID


class ExpectedVersion(BaseModel):
    version: int


class ChannelCreate(BaseModel):
    name: ChannelName
    topic: Topic | None = None


class ChannelUpdate(BaseModel):
    """Fields left out stay as they are; null clears the topic. A name cannot be null."""

    model_config = ConfigDict(extra="forbid")

    name: ChannelName | None = None
    topic: Topic | None = None
    version: int

    @field_validator("name")
    @classmethod
    def _name_is_not_cleared(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name cannot be null")
        return value


class ParticipantOut(BaseModel):
    """A person in a direct message (one who was deactivated stays listed), or its
    agent (`type` `agent`, listed after the people)."""

    id: uuid.UUID
    name: str
    is_active: bool
    type: PrincipalType = PrincipalType.USER

    @classmethod
    def of(cls, participant: Participant) -> "ParticipantOut":
        return cls(
            id=participant.id,
            name=participant.name,
            is_active=participant.is_active,
            type=participant.type,
        )


class InspectionNoteOut(BaseModel):
    """An admin looked into this direct message (spec 5.5): when, and who."""

    at: datetime
    admin_name: str


class ConversationOut(BaseModel):
    """`can_post`: whether the caller may write here now (the right in the space, and
    the channel not archived). `created_by` is null for what the system set up.
    `version` guards writes (send it back; stale → 409). A direct message lists its
    `participants` and, on its own (`GET /conversations/{id}`), every admin
    `inspections` of it; both are empty for other kinds. `page_id`: a page thread's
    page (null for other kinds)."""

    id: uuid.UUID
    kind: ConversationKind
    space_id: uuid.UUID | None
    page_id: uuid.UUID | None
    name: str | None
    topic: str | None
    archived_at: datetime | None
    created_by: PrincipalRef | None
    created_at: datetime
    version: int
    can_post: bool
    participants: list[ParticipantOut] = Field(default_factory=list)
    inspections: list[InspectionNoteOut] = Field(default_factory=list)

    @classmethod
    def of(
        cls,
        conversation: Conversation,
        *,
        can_post: bool,
        participants: Sequence[Participant] = (),
        inspections: Sequence[InspectionNote] = (),
    ) -> "ConversationOut":
        creator = None
        if conversation.created_by_type is not None and conversation.created_by_id is not None:
            creator = PrincipalRef(type=conversation.created_by_type, id=conversation.created_by_id)
        return cls(
            id=conversation.id,
            kind=conversation.kind,
            space_id=conversation.space_id,
            page_id=conversation.page_id,
            name=conversation.name,
            topic=conversation.topic,
            archived_at=conversation.archived_at,
            created_by=creator,
            created_at=conversation.created_at,
            version=conversation.version,
            can_post=can_post,
            participants=[ParticipantOut.of(p) for p in participants],
            inspections=[InspectionNoteOut(at=n.at, admin_name=n.admin_name) for n in inspections],
        )
