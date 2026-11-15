"""Access tokens for `/mcp` and the organisation's MCP settings (plan M8 decisions 2,
4 and 5).

A token is stored only as the SHA-256 of its clear text (`values.py`); the clear text
is shown once, when it is made. `kind` says whose it is: `personal` tokens act as
their person (`user_id`); `agent` tokens (an external agent's, plan M8 task 4) are
not made yet and never resolve until then. `space_ids` is the token's scope (None:
all the person's spaces), `mode` whether it may write at all.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.authorship import VIA_TOKEN_CHARS
from app.core.models_base import Base, OrgScoped, UuidPk, utcnow
from app.modules.ai.models import DataLocation

MAX_NAME_CHARS = VIA_TOKEN_CHARS  # what it writes carries its name (`core/authorship.py`)
MAX_SCOPE_SPACES = 50
MAX_DAYS = 365
DIGEST_BYTES = 32


class TokenKind(StrEnum):
    PERSONAL = "personal"
    AGENT = "agent"


class TokenMode(StrEnum):
    READ = "read"
    WRITE = "write"


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class AccessToken(UuidPk, OrgScoped, Base):
    __tablename__ = "access_token"
    __table_args__ = (
        CheckConstraint(_in("kind", TokenKind), name="kind"),
        CheckConstraint(_in("mode", TokenMode), name="mode"),
        CheckConstraint(f"octet_length(token_hash) = {DIGEST_BYTES}", name="token_hash"),
        CheckConstraint(
            f"space_ids IS NULL OR cardinality(space_ids) BETWEEN 1 AND {MAX_SCOPE_SPACES}",
            name="space_ids",
        ),
        CheckConstraint(f"expires_at <= created_at + interval '{MAX_DAYS} days'", name="expiry"),
        CheckConstraint("(kind = 'agent') = (agent_id IS NOT NULL)", name="agent"),
    )

    kind: Mapped[TokenKind] = mapped_column(String(16), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # An agent token's external agent (`kind = agent`, plan M8 decision 11); `user_id`
    # is then the agent's responsible person when it was issued.
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(MAX_NAME_CHARS), nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    space_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))
    mode: Mapped[TokenMode] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # To the minute, written at most once a minute (`resolve.py`).
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class McpSetting(Base):
    """Whether the organisation's members may use `/mcp` (`mcp.use`, all active members
    but guests), and the data location an MCP client counts as for the AI policy
    (decision 4). Without a row: off, `external`."""

    __tablename__ = "mcp_setting"
    __table_args__ = (CheckConstraint(_in("data_location", DataLocation), name="data_location"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    data_location: Mapped[DataLocation] = mapped_column(
        String(16), nullable=False, default=DataLocation.EXTERNAL, server_default="external"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
