import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models_base import Base, OrgScoped, UuidPk
from app.modules.users.models import User


class UserSession(UuidPk, OrgScoped, Base):
    """A login. The cookie carries a random token; only its SHA-256 is stored."""

    __tablename__ = "user_session"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    # The last request the session made (J7, HERD_SESSION_IDLE_HOURS): written when
    # it opens and then at most once a minute (`SessionRepository.touch`).
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # For the person's list of her sessions (J8): when it opened, and which browser on
    # which system (`device.device_hint`, no version; None for an unknown client).
    signed_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    device: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[User] = relationship(lazy="joined")
