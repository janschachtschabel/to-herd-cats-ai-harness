"""Automations and their log (plan M7 decisions 1 to 6, spec 8.4).

`automation`: work an agent does without being asked in a conversation, on behalf
of the person who owns it (`owner_user_id`: the run's asker, `run.user_id`), at a
place (`conversation_id`: the owner's DM with the agent, a channel of a space or a
ticket's thread; the run reads and writes by that place's rules, `agents/scope.py`),
with an instruction (`instruction`, the owner's words to the agent). Kinds:

- `once`: at one instant, `next_due_at`; after it fired (or was skipped) it is
  `done`, without a next term.
- `recurring`: a cron expression (`cron`) in an IANA zone (`time_zone`); after each
  firing `next_due_at` is the first term after "now" (`terms.py`).

Heartbeats and event rules come as further kinds with columns of their own.

`state`: `active` (fires when due), `paused` (`paused_reason`; keeps its next term,
fires nothing), `done` (a `once` that fired). `version` guards the owner's edits.

`automation_firing`: the log, one row per term that came due (`due_at`, the term;
`fired_at`, when the due loop took it): `started` with the run it started
(`run_id`), or why it started none (`skipped_busy`: the automation's previous run is
still open; `skipped_paused_agent`: the agent is not active). The unique index per
term backs up the row lock of the due loop: a term is logged once, whatever runs
how many times.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk
from app.modules.automations.terms import MAX_CRON_CHARS

MAX_INSTRUCTION_CHARS = 4_000
MAX_ZONE_CHARS = 64


class AutomationKind(StrEnum):
    ONCE = "once"
    RECURRING = "recurring"


class AutomationState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DONE = "done"


class PausedReason(StrEnum):
    MANUAL = "manual"  # someone allowed to paused it


class FiringOutcome(StrEnum):
    STARTED = "started"
    SKIPPED_BUSY = "skipped_busy"
    SKIPPED_PAUSED_AGENT = "skipped_paused_agent"


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class Automation(UuidPk, OrgScoped, Base):
    __tablename__ = "automation"
    __table_args__ = (
        CheckConstraint(_in("kind", AutomationKind), name="kind"),
        CheckConstraint(_in("state", AutomationState), name="state"),
        CheckConstraint(
            f"(state = 'paused') = (paused_reason IS NOT NULL) AND "
            f"(paused_reason IS NULL OR {_in('paused_reason', PausedReason)})",
            name="paused_reason",
        ),
        CheckConstraint("(kind = 'recurring') = (cron IS NOT NULL)", name="cron"),
        CheckConstraint("cron IS NULL OR time_zone IS NOT NULL", name="cron_zone"),
        CheckConstraint("kind <> 'once' OR time_zone IS NULL", name="once_zone"),
        CheckConstraint("(state = 'done') = (next_due_at IS NULL)", name="next_due"),
        CheckConstraint("state <> 'done' OR kind = 'once'", name="done"),
        CheckConstraint(
            f"char_length(instruction) BETWEEN 1 AND {MAX_INSTRUCTION_CHARS}", name="instruction"
        ),
        Index("ix_automation_due", "next_due_at", postgresql_where=text("state = 'active'")),
        Index("ix_automation_owner_user_id", "owner_user_id"),
        Index("ix_automation_agent_id", "agent_id"),
        Index("ix_automation_conversation_id", "conversation_id"),
    )

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[AutomationKind] = mapped_column(String(16), nullable=False)
    cron: Mapped[str | None] = mapped_column(String(MAX_CRON_CHARS))
    time_zone: Mapped[str | None] = mapped_column(String(MAX_ZONE_CHARS))
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[AutomationState] = mapped_column(String(16), nullable=False)
    paused_reason: Mapped[PausedReason | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AutomationFiring(UuidPk, OrgScoped, Base):
    __tablename__ = "automation_firing"
    __table_args__ = (
        CheckConstraint(_in("outcome", FiringOutcome), name="outcome"),
        CheckConstraint("run_id IS NULL OR outcome = 'started'", name="run"),
        Index("uq_automation_firing_term", "automation_id", "due_at", unique=True),
        Index("ix_automation_firing_run_id", "run_id"),
    )

    automation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("automation.id", ondelete="CASCADE"), nullable=False
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[FiringOutcome] = mapped_column(String(32), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("run.id", ondelete="SET NULL")
    )
