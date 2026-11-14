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
- `heartbeat`: every `interval_minutes` (15 to 1,440) inside its active hours: ISO
  weekdays (`active_days`) and a local `active_from`–`active_until` in `time_zone` (a
  window may pass midnight; equal: the whole day; `heartbeat_terms.py`). Its
  instruction is the checklist the agent goes through; an answer of exactly
  `HEARTBEAT_OK` is delivered nowhere (decision 7).

Event rules come as a further kind with columns of its own.

`state`: `active` (fires when due), `paused` (`paused_reason`: `manual`, `owner` (the
owner lost a right the automation needs, plan M7 decision 2) or `failing` (three runs
in a row did not end `completed`, decision 13); keeps its next term, fires nothing),
`done` (a `once` that fired), `deleted` (deleted through the API: it never fires
again and the API shows it no more, but its runs, their journal and its log stay as
history). `version` guards every change through the API and the take-over (409).

`automation_firing`: the log, one row per term that came due (`due_at`, the term;
`fired_at`, when the due loop took it): `started` with the run it started
(`run_id`, and the instruction it was given, `instruction`), or why it started none
(`skipped_busy`: the automation's previous run is still open; `skipped_paused_agent`:
the agent may not run; `skipped_budget`: a daily budget is reached;
`skipped_policy`: the place is closed to AI, archived, or its ticket is gone;
`skipped_off_hours`: a heartbeat's term taken up after its window closed, after an
outage; `skipped_depth`: an event a run caused at the end of a chain of three, plan
M7 decision 9). A heartbeat's run that answered `HEARTBEAT_OK` marks its row
(`heartbeat_ok`): nothing was delivered. A
term at which the owner turned out to have lost a right it needs logs nothing: the
automation is paused (`paused_reason = owner`) and keeps the term. The unique index per
term backs up the row lock of the due loop: a term is logged once, whatever runs
how many times.
"""

import uuid
from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk
from app.modules.automations.heartbeat_terms import MAX_INTERVAL_MINUTES, MIN_INTERVAL_MINUTES
from app.modules.automations.terms import MAX_CRON_CHARS
from app.modules.tickets.models import TicketKind

MAX_INSTRUCTION_CHARS = 4_000
MAX_ZONE_CHARS = 64
MIN_QUIET_SECONDS = 60
MAX_QUIET_SECONDS = 86_400
DEFAULT_QUIET_SECONDS = 300


class AutomationKind(StrEnum):
    ONCE = "once"
    RECURRING = "recurring"
    HEARTBEAT = "heartbeat"
    EVENT = "event"


class EventType(StrEnum):
    """What an event rule listens to (decision 8)."""

    PAGE_PUBLISHED = "page.published"
    TICKET_CREATED = "ticket.created"
    ATTACHMENT_UPLOADED = "attachment.uploaded"
    PAGE_REVIEW_DUE = "page.review_due"


class AutomationState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DONE = "done"
    DELETED = "deleted"  # gone for the API; its runs and log stay as history


class PausedReason(StrEnum):
    MANUAL = "manual"  # someone allowed to paused it
    OWNER = "owner"  # its owner no longer acts, has no AI, or reaches agent or place no more
    FAILING = "failing"  # three runs in a row did not end `completed`


class FiringOutcome(StrEnum):
    STARTED = "started"
    SKIPPED_BUSY = "skipped_busy"
    SKIPPED_PAUSED_AGENT = "skipped_paused_agent"
    SKIPPED_BUDGET = "skipped_budget"  # a daily budget of the owner, agent or org is reached
    SKIPPED_POLICY = "skipped_policy"  # the place closed to AI, archived, or its ticket gone
    SKIPPED_OFF_HOURS = "skipped_off_hours"  # a heartbeat's term taken up after its window
    SKIPPED_DEPTH = "skipped_depth"  # an event a run caused at the end of a chain of three


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
        CheckConstraint(
            "kind = 'event' OR state = 'deleted' OR (state = 'done') = (next_due_at IS NULL)",
            name="next_due",
        ),
        CheckConstraint("state <> 'done' OR kind = 'once'", name="done"),
        CheckConstraint(
            f"char_length(instruction) BETWEEN 1 AND {MAX_INSTRUCTION_CHARS}", name="instruction"
        ),
        CheckConstraint("failures >= 0", name="failures"),
        CheckConstraint(
            "(kind = 'heartbeat') = (interval_minutes IS NOT NULL) AND "
            "(kind = 'heartbeat') = (active_days IS NOT NULL) AND "
            "(kind = 'heartbeat') = (active_from IS NOT NULL) AND "
            "(kind = 'heartbeat') = (active_until IS NOT NULL) AND "
            "(kind <> 'heartbeat' OR time_zone IS NOT NULL)",
            name="heartbeat",
        ),
        CheckConstraint(
            f"interval_minutes BETWEEN {MIN_INTERVAL_MINUTES} AND {MAX_INTERVAL_MINUTES}",
            name="interval_minutes",
        ),
        CheckConstraint(
            "cardinality(active_days) BETWEEN 1 AND 7 AND "
            "active_days <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::smallint[]",
            name="active_days",
        ),
        CheckConstraint(
            "(kind = 'event') = (event_type IS NOT NULL) AND "
            "(kind = 'event') = (quiet_seconds IS NOT NULL) AND "
            "(kind <> 'event' OR time_zone IS NULL) AND "
            "(kind = 'event' OR quiet_until IS NULL)",
            name="event",
        ),
        CheckConstraint(_in("event_type", EventType), name="event_type"),
        CheckConstraint(
            f"quiet_seconds BETWEEN {MIN_QUIET_SECONDS} AND {MAX_QUIET_SECONDS}",
            name="quiet_seconds",
        ),
        CheckConstraint(
            "(filter_tag_id IS NULL AND filter_ticket_kind IS NULL) OR "
            "event_type = 'ticket.created'",
            name="event_filter",
        ),
        CheckConstraint(_in("filter_ticket_kind", TicketKind), name="filter_ticket_kind"),
        Index(
            "ix_automation_event_type",
            "org_id",
            "event_type",
            postgresql_where=text("kind = 'event' AND state = 'active'"),
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
    # Runs in a row that did not end `completed` (decision 13): the third pauses it
    # (`failing`); a completed run, that pause and a take-over set it back to 0.
    failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    # A heartbeat's (decision 7): its interval and active hours (`heartbeat_terms.Hours`).
    interval_minutes: Mapped[int | None] = mapped_column(Integer)
    active_days: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger))
    active_from: Mapped[time | None] = mapped_column(Time)
    active_until: Mapped[time | None] = mapped_column(Time)
    # An event rule's (decisions 8 and 9).
    event_type: Mapped[EventType | None] = mapped_column(String(32))
    quiet_seconds: Mapped[int | None] = mapped_column(Integer)
    quiet_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filter_tag_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    filter_ticket_kind: Mapped[TicketKind | None] = mapped_column(String(16))


class AutomationFiring(UuidPk, OrgScoped, Base):
    __tablename__ = "automation_firing"
    __table_args__ = (
        CheckConstraint(_in("outcome", FiringOutcome), name="outcome"),
        CheckConstraint("run_id IS NULL OR outcome = 'started'", name="run"),
        CheckConstraint("(outcome = 'started') = (instruction IS NOT NULL)", name="instruction"),
        CheckConstraint("NOT heartbeat_ok OR outcome = 'started'", name="heartbeat_ok"),
        Index("uq_automation_firing_term", "automation_id", "due_at", unique=True),
        Index("ix_automation_firing_run_id", "run_id"),
        Index("ix_automation_firing_fired_at", "fired_at"),  # retention (`upkeep_repository`)
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
    # What the started run was asked: the automation's instruction as the term fired,
    # so every take-up of the run reads the same, whatever the owner edits meanwhile.
    instruction: Mapped[str | None] = mapped_column(Text)
    # A heartbeat's run answered `HEARTBEAT_OK`: nothing was delivered (decision 7).
    heartbeat_ok: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
