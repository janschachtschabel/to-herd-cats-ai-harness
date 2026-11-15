"""Bodies of the internal collab API (`collab_router.py`). A grant is the text the relay
handed the collab process (`collab_grants.py`); any other text is simply not found."""

import uuid
from typing import Annotated

from pydantic import BaseModel, Field

from app.modules.wiki.collab_grants import MAX_GRANT_CHARS

MAX_EDITORS = 200

GrantText = Annotated[str, Field(min_length=1, max_length=MAX_GRANT_CHARS)]


class AuthIn(BaseModel):
    """The connection's grant, and the page and generation of its URL."""

    grant: GrantText
    page_id: uuid.UUID
    generation: int = Field(ge=0)


class CollabUserOut(BaseModel):
    id: uuid.UUID
    name: str


class AuthOut(BaseModel):
    """`session_ref` names the connection's login session opaquely, for the collab
    process's limits per session; `generation` is the page's."""

    user: CollabUserOut
    session_ref: str
    generation: int
    can_edit: bool


class LiveDocumentOut(BaseModel):
    generation: int
    ydoc_b64: str | None
    content_md: str
    title: str


class SaveIn(BaseModel):
    """State and Markdown are bounded by the internal body limit only: their own
    limits answer 413 `collab.state_too_large` (`CollabService`), which the live
    editor shows as "too large for live editing" (review M2 R8)."""

    generation: int = Field(ge=0)
    ydoc_b64: str
    content_md: str
    editor_grants: list[GrantText] = Field(min_length=1, max_length=MAX_EDITORS)
    session_key: str = Field(min_length=1, max_length=100)


class SaveOut(BaseModel):
    generation: int
    version: int  # the page's version after the save


class CheckIn(BaseModel):
    """`grants`: the document's connections; `unsaved_grants`: the grants whose edits
    are in the document but not saved yet (one of them revoked ends the generation,
    if it was issued for this page and generation)."""

    grants: list[GrantText] = Field(max_length=MAX_EDITORS)
    unsaved_grants: list[GrantText] = Field(default=[], max_length=MAX_EDITORS)
    generation: int = Field(ge=0)


class CheckOut(BaseModel):
    """`revoked_grants`: connections to close (no right any more, or no grant of this
    page and generation); `ended_grants`: login sessions that ended (logout, expiry) of
    people who may still edit: their edits may be saved, then their connections close
    (4401)."""

    generation_ok: bool
    generation: int
    revoked_grants: list[str]
    ended_grants: list[str]
