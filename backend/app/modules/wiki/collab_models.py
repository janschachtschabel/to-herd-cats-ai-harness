"""The state of a page's live-editing session (spec 9): the Yjs document as the collab
process last saved it, for the generation it belongs to. Session state only: the page's
content is its Markdown; a state of an older generation is never handed out again.
And the grants the collab process acts under (`CollabGrant`, `collab_grants.py`), the
collab instances and which of them owns a page (`CollabInstance`, `CollabPageOwner`,
`collab_instances.py`)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String
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


class CollabInstance(Base):
    """A collab process that announced itself (plan M9 decision 17): where the relay
    reaches it (`url`, from HERD_COLLAB_ADVERTISE_URL), when it last did (every 5 s;
    silent for INSTANCE_TTL it counts as gone) and whether it is draining (stopping: it
    gets no new pages). Infrastructure shared by every organisation, so no `org_id`
    (an explicit decision of the plan); the process picks its own `id` at start."""

    __tablename__ = "collab_instance"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    url: Mapped[str] = mapped_column(String(256), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    draining: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CollabPageOwner(OrgScoped, Base):
    """The one collab instance that holds a page's live document (plan M9 decision 17).
    The binding lasts OWNER_TTL from the owner's last call (its checks come every 5 s);
    whoever takes the page over raises `epoch`, and only the owner with the current
    epoch may save or check. The row stays with its page, so the epoch only rises; an
    instance that is gone leaves `instance_id` NULL."""

    __tablename__ = "collab_page_owner"

    page_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), primary_key=True
    )
    instance_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("collab_instance.id", ondelete="SET NULL"), index=True
    )
    epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
