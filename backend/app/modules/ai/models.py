"""AI connections (spec 7.1) and who uses which (spec 7.2).

`secret_ref` is a reference (`env:HERD_AI_*` or `enc:<token>`, `core/secrets.py`), never
the key itself; NULL for a provider that needs none (a local server). `models` are the
model names (for `b_api`: route names) the connection offers, in order: the first is
the connection's standard model. `kind` decides the egress rules (`local`: http and
private addresses) and whether calls may stream (`b_api`: never).
"""

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk

MAX_NAME_CHARS = 120
MAX_URL_CHARS = 500
MAX_MODEL_CHARS = 200
MAX_MODELS = 500
MAX_EXTRA_BODY_CHARS = 4000
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-6-luna"


class ConnectionKind(StrEnum):
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    B_API = "b_api"  # `model` carries a route name; no streaming
    LOCAL = "local"  # may use http and private addresses


class ParamFamily(StrEnum):
    MAX_COMPLETION_TOKENS = "max_completion_tokens"  # GPT-5/6
    MAX_TOKENS = "max_tokens"  # older and open models


class DataLocation(StrEnum):
    LOCAL = "local"
    EU = "eu"
    EXTERNAL = "external"


class Purpose(StrEnum):
    CHAT = "chat"
    EMBEDDING = "embedding"
    BOTH = "both"


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class AiConnection(UuidPk, OrgScoped, Timestamps, Base):
    __tablename__ = "ai_connection"
    __table_args__ = (
        UniqueConstraint("org_id", "name"),
        CheckConstraint(_in("kind", ConnectionKind), name="kind"),
        CheckConstraint(_in("param_family", ParamFamily), name="param_family"),
        CheckConstraint(_in("data_location", DataLocation), name="data_location"),
        CheckConstraint(_in("purpose", Purpose), name="purpose"),
        CheckConstraint(
            "secret_ref IS NULL OR secret_ref LIKE 'env:%' OR secret_ref LIKE 'enc:%'",
            name="secret_ref",
        ),
        CheckConstraint("max_concurrency BETWEEN 1 AND 100", name="max_concurrency"),
        CheckConstraint("requests_per_minute BETWEEN 1 AND 100000", name="requests_per_minute"),
    )

    name: Mapped[str] = mapped_column(String(MAX_NAME_CHARS), nullable=False)
    kind: Mapped[ConnectionKind] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str] = mapped_column(String(MAX_URL_CHARS), nullable=False)
    secret_ref: Mapped[str | None] = mapped_column(Text)
    models: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    param_family: Mapped[ParamFamily] = mapped_column(String(32), nullable=False)
    extra_body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    supports_tools: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    data_location: Mapped[DataLocation] = mapped_column(String(16), nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    requests_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    purpose: Mapped[Purpose] = mapped_column(String(16), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Bumped by every write; a write names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OrgAssignment(Base):
    """The organisation's standard assignment (spec 7.2): a chat connection and a model,
    or none (then nobody has AI until an admin assigns some). `version` also guards
    the ordered list of group assignments, which is replaced as a whole."""

    __tablename__ = "ai_org_assignment"
    __table_args__ = (CheckConstraint("(connection_id IS NULL) = (model IS NULL)", name="target"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), primary_key=True
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_connection.id", ondelete="RESTRICT"), index=True
    )
    model: Mapped[str | None] = mapped_column(String(MAX_MODEL_CHARS))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class GroupAssignment(OrgScoped, Base):
    """A group's assignment; for a person in several groups the lowest `position`
    wins."""

    __tablename__ = "ai_group_assignment"
    __table_args__ = (UniqueConstraint("org_id", "position"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_group.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_connection.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(MAX_MODEL_CHARS), nullable=False)


class UserAssignment(OrgScoped, Base):
    """A person's own assignment: a connection and a model, or expressly no AI."""

    __tablename__ = "ai_user_assignment"
    __table_args__ = (
        CheckConstraint("(connection_id IS NULL) = (model IS NULL)", name="target"),
        CheckConstraint("no_ai = (connection_id IS NULL)", name="no_ai"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    no_ai: Mapped[bool] = mapped_column(Boolean, nullable=False)
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_connection.id", ondelete="RESTRICT"), index=True
    )
    model: Mapped[str | None] = mapped_column(String(MAX_MODEL_CHARS))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
