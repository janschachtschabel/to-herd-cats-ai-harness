"""The state of a page's live-editing session (spec 9): the Yjs document as the collab
process last saved it, for the generation it belongs to. Session state only: the page's
content is its Markdown; a state of an older generation is never handed out again."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, utcnow

MAX_YDOC_BYTES = 5 * 1024 * 1024


class PageCollabState(OrgScoped, Base):
    __tablename__ = "page_collab_state"

    page_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), primary_key=True
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    ydoc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
