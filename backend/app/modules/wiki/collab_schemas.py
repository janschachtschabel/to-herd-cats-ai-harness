"""Bodies of the internal collab API (`collab_router.py`)."""

import uuid

from pydantic import BaseModel, Field

from app.modules.wiki.collab_models import MAX_YDOC_BYTES
from app.modules.wiki.models import MAX_CONTENT_CHARS

# Room for base64 of a state somewhat over the limit, so the limit answers 413.
_MAX_YDOC_B64_CHARS = (MAX_YDOC_BYTES // 3 + 2) * 4 + 1024
MAX_EDITORS = 200


class AuthIn(BaseModel):
    session_token: str = Field(min_length=1, max_length=200)
    page_id: uuid.UUID


class CollabUserOut(BaseModel):
    id: uuid.UUID
    name: str


class AuthOut(BaseModel):
    """`session_id` names the connection's login session in later saves and checks."""

    user: CollabUserOut
    session_id: uuid.UUID
    generation: int
    can_edit: bool


class LiveDocumentOut(BaseModel):
    generation: int
    ydoc_b64: str | None
    content_md: str
    title: str


class SaveIn(BaseModel):
    generation: int = Field(ge=0)
    ydoc_b64: str = Field(max_length=_MAX_YDOC_B64_CHARS)
    content_md: str = Field(max_length=MAX_CONTENT_CHARS)
    editor_session_ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_EDITORS)
    session_key: str = Field(min_length=1, max_length=100)


class SaveOut(BaseModel):
    generation: int
    version: int  # the page's version after the save


class CheckIn(BaseModel):
    """`session_ids`: the document's connections; `unsaved_session_ids`: the sessions
    whose edits are in the document but not saved yet (one of them revoked ends the
    generation)."""

    session_ids: list[uuid.UUID] = Field(max_length=MAX_EDITORS)
    unsaved_session_ids: list[uuid.UUID] = Field(default=[], max_length=MAX_EDITORS)
    generation: int = Field(ge=0)


class CheckOut(BaseModel):
    """`ended_session_ids`: sessions that ended (logout, expiry) of people who may still
    edit: their edits may be saved, then their connections close (4401)."""

    generation_ok: bool
    generation: int
    revoked_session_ids: list[uuid.UUID]
    revoked_user_ids: list[uuid.UUID]
    ended_session_ids: list[uuid.UUID]
