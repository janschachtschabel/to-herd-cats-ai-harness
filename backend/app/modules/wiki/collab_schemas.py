"""Bodies of the internal collab API (`collab_router.py`). A grant is the text the relay
handed the collab process (`collab_grants.py`); any other text is simply not found."""

import uuid
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from app.modules.wiki.collab_grants import MAX_GRANT_CHARS

MAX_EDITORS = 200

GrantText = Annotated[str, Field(min_length=1, max_length=MAX_GRANT_CHARS)]
# Where the relay reaches a collab instance: ws:// or wss://, host and port, no path
# (HERD_COLLAB_ADVERTISE_URL; the relay adds `/collab/<page id>`).
InstanceUrl = Annotated[str, Field(max_length=256, pattern=r"^wss?://[A-Za-z0-9.\-\[\]:]+$")]


class InstanceIn(BaseModel):
    """A collab instance's heartbeat (plan M9 decision 17): the id it picked at start,
    its address, and whether it is draining (it stays so)."""

    id: uuid.UUID
    url: InstanceUrl
    draining: bool = False


class Owned(BaseModel):
    """The instance a save or check comes from and the epoch it loaded the page with;
    both or neither (a collab process of 1.0.0 names none)."""

    instance_id: uuid.UUID | None = None
    epoch: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def both_or_neither(self) -> Self:
        if (self.instance_id is None) != (self.epoch is None):
            raise ValueError("instance_id and epoch go together")
        return self


class AuthIn(BaseModel):
    """The connection's grant, and the page and generation of its URL."""

    grant: GrantText
    page_id: uuid.UUID
    generation: int = Field(ge=0)
    instance_id: uuid.UUID | None = None  # the collab instance asking (none: 1.0.0)


class CollabUserOut(BaseModel):
    id: uuid.UUID
    name: str


class AuthOut(BaseModel):
    """`session_ref` names the connection's login session opaquely, for the collab
    process's limits per session; `generation` is the page's; `epoch` the asking
    instance's binding to the page (None for a caller that named no instance)."""

    user: CollabUserOut
    session_ref: str
    generation: int
    can_edit: bool
    epoch: int | None


class LiveDocumentOut(BaseModel):
    generation: int
    ydoc_b64: str | None
    content_md: str
    title: str
    epoch: int | None  # the loading instance's binding (saves and checks name it)


class SaveIn(Owned):
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


class CheckIn(Owned):
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
    (4401). `maintenance`: the installation is in maintenance (plan M9 decision 9):
    close every connection (4503) and drop the document unsaved."""

    generation_ok: bool
    generation: int
    revoked_grants: list[str]
    ended_grants: list[str]
    maintenance: bool = False
