import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.principal import Principal, PrincipalType
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

    @classmethod
    def of(cls, principal: Principal) -> "PrincipalRef":
        return cls(type=principal.type, id=principal.id)


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


class ConversationOut(BaseModel):
    """`can_post`: whether the caller may write here now (the right in the space, and
    the channel not archived). `created_by` is null for what the system set up.
    `version` guards writes (send it back; stale → 409)."""

    id: uuid.UUID
    kind: ConversationKind
    space_id: uuid.UUID | None
    name: str | None
    topic: str | None
    archived_at: datetime | None
    created_by: PrincipalRef | None
    created_at: datetime
    version: int
    can_post: bool

    @classmethod
    def of(cls, conversation: Conversation, *, can_post: bool) -> "ConversationOut":
        creator = None
        if conversation.created_by_type is not None and conversation.created_by_id is not None:
            creator = PrincipalRef(type=conversation.created_by_type, id=conversation.created_by_id)
        return cls(
            id=conversation.id,
            kind=conversation.kind,
            space_id=conversation.space_id,
            name=conversation.name,
            topic=conversation.topic,
            archived_at=conversation.archived_at,
            created_by=creator,
            created_at=conversation.created_at,
            version=conversation.version,
            can_post=can_post,
        )
