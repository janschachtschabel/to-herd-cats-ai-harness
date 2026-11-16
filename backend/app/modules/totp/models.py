"""The second factor of a password account (plan M9 task 16, Jan's answer J3: optional
for everyone): its TOTP secret, its recovery codes, and the sign-ins waiting for it."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk


class UserTotp(UuidPk, OrgScoped, Base):
    """One per person. `secret_ref` is `enc:` under `HERD_SECRET_KEY`, never returned
    after setup. Without `confirmed_at` the setup waits for its first code and the
    secret protects nothing yet. `last_step`: the newest time step a code was accepted
    for; no code of it or an earlier step is accepted again (ASVS 5.0 V6.5.1)."""

    __tablename__ = "user_totp"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    secret_ref: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_step: Mapped[int | None] = mapped_column(BigInteger)


class TotpRecoveryCode(UuidPk, OrgScoped, Base):
    """A recovery code: only its SHA-256 (each code has 120 random bits, ASVS 5.0
    V6.5.2); the row is deleted by the statement that accepts the code."""

    __tablename__ = "totp_recovery_code"
    __table_args__ = (UniqueConstraint("user_id", "code_hash"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class SignInChallenge(UuidPk, OrgScoped, Base):
    """A sign-in whose first step (password or OIDC) passed and that waits for the
    second factor: no session yet. The browser holds a random token in an HttpOnly
    cookie; only its SHA-256 is stored. Used once, for `CHALLENGE_MINUTES`; after
    `MAX_CHALLENGE_FAILURES` wrong codes it is gone."""

    __tablename__ = "sign_in_challenge"
    __table_args__ = (CheckConstraint("method IN ('password', 'oidc')", name="method"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
