import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.messaging.dms import DmEntry
from app.modules.messaging.models import MAX_DM_PEOPLE, MAX_REASON_CHARS, DmInspection
from app.modules.messaging.schemas import ConversationOut, ParticipantOut

MIN_REASON_CHARS = 10

Reason = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=MIN_REASON_CHARS, max_length=MAX_REASON_CHARS
    ),
]


class DmOpen(BaseModel):
    """The other people (the caller is added); 2 to 9 people in all."""

    model_config = ConfigDict(extra="forbid")

    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_DM_PEOPLE)


class DmOut(ConversationOut):
    """A direct message in the caller's list: `last_message_at` is its newest
    top-level message (null before the first)."""

    last_message_at: datetime | None

    @classmethod
    def of_entry(cls, entry: DmEntry) -> "DmOut":
        base = ConversationOut.of(
            entry.conversation, can_post=True, participants=entry.participants
        )
        return cls(**base.model_dump(), last_message_at=entry.last_message_at)


class InspectableDmOut(BaseModel):
    """What an inspecting admin learns before an inspection: who, and when, no content."""

    conversation_id: uuid.UUID
    participants: list[ParticipantOut]
    created_at: datetime
    last_message_at: datetime | None

    @classmethod
    def of(cls, entry: DmEntry) -> "InspectableDmOut":
        return cls(
            conversation_id=entry.conversation.id,
            participants=[ParticipantOut.of(p) for p in entry.participants],
            created_at=entry.conversation.created_at,
            last_message_at=entry.last_message_at,
        )


class InspectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID
    reason: Reason


class InspectionOut(BaseModel):
    """Read the DM's messages at `/admin/dm-inspect/{id}/messages` until `expires_at`."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    reason: str
    granted_at: datetime
    expires_at: datetime

    @classmethod
    def of(cls, inspection: DmInspection) -> "InspectionOut":
        return cls(
            id=inspection.id,
            conversation_id=inspection.conversation_id,
            reason=inspection.reason,
            granted_at=inspection.granted_at,
            expires_at=inspection.expires_at,
        )
