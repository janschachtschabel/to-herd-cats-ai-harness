"""The state of a page's live-editing session (spec 9): the Yjs document as the collab
process last saved it, for the generation it belongs to. Session state only: the page's
content is its Markdown; a state of an older generation is never handed out again.
And the grants the collab process acts under (`CollabGrant`, `collab_grants.py`)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk

MAX_YDOC_BYTES = 5 * 1024 * 1024


class PageCollabState(OrgScoped, Base):
    __tablename__ = "page_collab_state"

    page_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), primary_key=True
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    ydoc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class CollabGrant(UuidPk, OrgScoped, Base):
    """What the collab process holds for one live connection instead of the session
    cookie (plan M9 decision 16, R14): good for exactly one page and generation, for
    ten minutes from the last check that named it. Only the SHA-256 of the token is
    stored. When its login session is deleted (revocation, or an hour after a logout)
    the grant loses every power (`session_id` NULL) but stays until it is cleared away,
    so a check can still tell that unsaved edits came through it and end the
    generation; a grant no one issued for the page and generation ends nothing."""

    __tablename__ = "collab_grant"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_session.id", ondelete="SET NULL"), index=True
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), index=True
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
