"""Agents and their runs (spec 5.1, 8.1, 8.3; plan M5 decision 2).

`agent`: a principal (`agent:<id>`) with the fields M5 reads: name, a short
introduction for colleagues, instructions, the connection and model it talks to, the
person responsible for it, a status (`draft`: not offered to anyone; `active`;
`paused`: kept, but starts no runs) and its limits per run (steps, runtime), capped
from above; its autonomy level (spec 8.2: 1 reads, 2 proposes, 3 writes inside, 4
acts outside through external tools, plan M8 decision 8), the default of its tool
grants.

An external agent (`kind = external`, plan M8 decision 11) is a principal with
memberships like every agent, but has no connection, no model and no runs in the
system: it works from outside through `/mcp` with an agent token
(`modules/tokens`), at level 2 at most, never a personal agent. Its responsible
person's rights bound what its tokens may do; while that person is inactive, or the
agent paused, its tokens rest.

A personal agent (`owner_user_id`, plan M6 decision 13) belongs to one person: it is
a member only of that person's personal space, its responsible person is its owner,
it has at most level 2 and uses the owner's connection and model (`personal.py`).

`agent_tool`: an agent's entry for one tool of the catalog (`toolbox/catalog.py`) or
one external tool (`toolbox/external.py`, by its name `ext_…`): `allow`, `confirm` or
`block`; it can only tighten what the level allows (`toolbox/policy.py`), and an
external tool is offered only with one.

Runs and their journal (`run`, `run_event`): `run_models.py`;
`run_cancel_request` and `ai_rate_window`: `run_control_models.py`.
"""

import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk

MAX_NAME_CHARS = 120
MAX_INTRO_CHARS = 500
MAX_INSTRUCTIONS_CHARS = 20_000
MAX_STEPS = 25
MAX_RUNTIME_SECONDS = 600
MAX_LEVEL = 4  # 4: acting outside (external write tools, plan M8 decision 8)
DEFAULT_LEVEL = 2
EXTERNAL_MAX_LEVEL = 2  # an external agent proposes at most (plan M8 decision 11)


class AgentKind(StrEnum):
    INTERNAL = "internal"  # run by the worker on a connection and model
    EXTERNAL = "external"  # works from outside through `/mcp` (plan M8 decision 11)


class AgentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class Agent(UuidPk, OrgScoped, Timestamps, Base):
    __tablename__ = "agent"
    __table_args__ = (
        CheckConstraint(_in("status", AgentStatus), name="status"),
        CheckConstraint(f"char_length(instructions) <= {MAX_INSTRUCTIONS_CHARS}", name="instr"),
        CheckConstraint(f"max_steps BETWEEN 1 AND {MAX_STEPS}", name="max_steps"),
        CheckConstraint(
            f"max_runtime_seconds BETWEEN 10 AND {MAX_RUNTIME_SECONDS}", name="max_runtime"
        ),
        CheckConstraint(f"level BETWEEN 1 AND {MAX_LEVEL}", name="level"),
        CheckConstraint(_in("kind", AgentKind), name="kind"),
        CheckConstraint(
            "kind = 'external' OR (connection_id IS NOT NULL AND model IS NOT NULL)",
            name="internal_target",
        ),
        CheckConstraint(
            "kind = 'internal' OR (connection_id IS NULL AND model IS NULL"
            f" AND owner_user_id IS NULL AND level <= {EXTERNAL_MAX_LEVEL})",
            name="external_fields",
        ),
        Index("ix_agent_connection_id", "connection_id"),
        Index("ix_agent_owner_user_id", "owner_user_id"),
    )

    name: Mapped[str] = mapped_column(String(MAX_NAME_CHARS), nullable=False)
    kind: Mapped[AgentKind] = mapped_column(
        String(16), nullable=False, default=AgentKind.INTERNAL, server_default="internal"
    )
    intro: Mapped[str] = mapped_column(String(MAX_INTRO_CHARS), nullable=False, default="")
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # NULL only for an external agent (`kind`).
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_connection.id", ondelete="RESTRICT")
    )
    model: Mapped[str | None] = mapped_column(String(200))
    responsible_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    # A personal agent's owner (plan M6 decision 13; `personal.py`); NULL for the
    # organisation's agents.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id")
    )
    status: Mapped[AgentStatus] = mapped_column(String(16), nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=MAX_STEPS)
    max_runtime_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=MAX_RUNTIME_SECONDS
    )
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_LEVEL, server_default=text(str(DEFAULT_LEVEL))
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    @property
    def external(self) -> bool:
        return self.kind == AgentKind.EXTERNAL


class AgentTool(OrgScoped, Base):
    __tablename__ = "agent_tool"
    __table_args__ = (CheckConstraint("policy IN ('allow', 'confirm', 'block')", name="policy"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent.id", ondelete="CASCADE"), primary_key=True
    )
    tool: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy: Mapped[str] = mapped_column(String(16), nullable=False)
