"""Agents and their runs (spec 5.1, 8.1, 8.3; plan M5 decision 2).

`agent`: a principal (`agent:<id>`) with the fields M5 reads: name, a short
introduction for colleagues, instructions, the connection and model it talks to, the
person responsible for it, a status (`draft`: not offered to anyone; `active`;
`paused`: kept, but starts no runs) and its limits per run (steps, runtime), capped
from above; its autonomy level (spec 8.2: 1 reads, 2 proposes, 3 writes inside; 4,
acting outside, comes with M8), the default of its tool grants.

A personal agent (`owner_user_id`, plan M6 decision 13) belongs to one person: it is
a member only of that person's personal space, its responsible person is its owner,
it has at most level 2 and uses the owner's connection and model (`personal.py`).

`agent_tool`: an agent's entry for one tool of the catalog (`toolbox/catalog.py`):
`allow`, `confirm` or `block`; it can only tighten what the level allows
(`toolbox/policy.py`).

`run`: one answer to a direct message, to a mention of the agent in a channel or a
thread (it answers in the mentioning message's thread), or to a ticket assigned to it
(`work_item_id`: its task; it answers in the ticket's thread, `triggers.py`). Created
`queued` in the transaction of the message or the assignment that asks
(`trigger_message_id`: the message; none for an assignment); `chain_depth` counts the
handovers from agent to agent that led to it (at most `MAX_CHAIN_DEPTH`). A worker
takes it (`running`, with a lease it renews) and ends it (`done`, with `stop_reason`).
A run that needs an answer from a person (a release, a question: plan M6 decision 1)
is `waiting` until `wait_until`, holding nothing; the answer makes it `queued` again
(`control.resume_waiting`), the run loop ends it with `waiting_timeout` once
`wait_until` has passed. A lane has at most one active run, running or waiting, and
at most one queued run per agent (unique partial indexes over `LANE`): a message that
arrives while one is queued is answered by it, one that arrives while one runs gets
the next, one that arrives while one waits gets none (`run.waiting`). The lane is the
thread of the mentioning message in a channel (`lane_id`, its root), else the
conversation (a DM, a page thread, a ticket thread: one per ticket), so a run waiting
for a release holds its thread, not the whole channel. Queued runs count per agent
because of handovers: the next agent's run waits queued behind the run that handed
the ticket over, and that run may itself wait and be queued again.

Every take-up by a worker counts in `attempt`; `recoveries` counts those after a lost
lease (its worker died), which are limited. `started_at` is the first take-up: the
conversation a run answers ends there, whatever take-up works on it.

`run_event`: the run's journal (plan M6 decision 1), one continuous sequence (`seq`,
counted on across take-ups; `attempt` notes the take-up that wrote it; the stop is
`seq` 0): model calls with their answer and usage, tool calls with their full
arguments and results, the stop. A run taken up again replays it and goes on after
its last step. Content lives only here, never in logs or metrics; readable by the
person who asked, the person responsible and those with `agent.manage`.

`run_cancel_request`: someone asked a run to stop (spec 8.3); checked before every
step and in the transaction that ends the run (`cancelled`).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk, utcnow

MAX_NAME_CHARS = 120
MAX_INTRO_CHARS = 500
MAX_INSTRUCTIONS_CHARS = 20_000
MAX_STEPS = 25
MAX_RUNTIME_SECONDS = 600
MAX_LEVEL = 3  # level 4 (external tools) comes with M8
MAX_CHAIN_DEPTH = 3  # handovers from agent to agent that led to a run (plan M6 task 8)
DEFAULT_LEVEL = 2


class AgentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"


class RunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    DONE = "done"


class StopReason(StrEnum):
    COMPLETED = "completed"
    MAX_STEPS = "max_steps"
    DEADLINE = "deadline"
    NO_PROGRESS = "no_progress"  # the third identical tool call
    RIGHTS_REVOKED = "rights_revoked"
    POLICY_BLOCKED = "policy_blocked"
    PROVIDER_REFUSED = "provider_refused"  # 401, 402, 403, 429
    ERROR = "error"
    CANCELLED = "cancelled"  # a `run_cancel_request`
    WAITING_TIMEOUT = "waiting_timeout"  # nobody answered by `wait_until`
    APPROVAL_EXPIRED = "approval_expired"  # nobody decided a release in time (task 7)


class EventKind(StrEnum):
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    STOP = "stop"


# Where "one open run" counts: a channel thread's root (`Run.lane_id`), else the
# conversation.
LANE = text("COALESCE(lane_id, conversation_id)")


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
        Index("ix_agent_connection_id", "connection_id"),
        Index("ix_agent_owner_user_id", "owner_user_id"),
    )

    name: Mapped[str] = mapped_column(String(MAX_NAME_CHARS), nullable=False)
    intro: Mapped[str] = mapped_column(String(MAX_INTRO_CHARS), nullable=False, default="")
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    connection_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_connection.id", ondelete="RESTRICT"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(200), nullable=False)
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


class AgentTool(OrgScoped, Base):
    __tablename__ = "agent_tool"
    __table_args__ = (CheckConstraint("policy IN ('allow', 'confirm', 'block')", name="policy"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent.id", ondelete="CASCADE"), primary_key=True
    )
    tool: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy: Mapped[str] = mapped_column(String(16), nullable=False)


class Run(UuidPk, OrgScoped, Base):
    __tablename__ = "run"
    __table_args__ = (
        CheckConstraint(_in("state", RunState), name="state"),
        CheckConstraint(
            f"(state = 'done') = (stop_reason IS NOT NULL) AND "
            f"(stop_reason IS NULL OR {_in('stop_reason', StopReason)})",
            name="stop_reason",
        ),
        CheckConstraint("(state = 'running') = (lease_until IS NOT NULL)", name="lease"),
        CheckConstraint("(state = 'waiting') = (wait_until IS NOT NULL)", name="wait"),
        Index(
            "uq_run_queued_per_lane",
            LANE,
            "agent_id",
            unique=True,
            postgresql_where=text("state = 'queued'"),
        ),
        Index(
            "uq_run_running_per_lane",
            LANE,
            unique=True,
            postgresql_where=text("state = 'running'"),
        ),
        Index(
            "uq_run_active_per_lane",
            LANE,
            unique=True,
            postgresql_where=text("state IN ('running', 'waiting')"),
        ),
        Index("ix_run_open", "created_at", postgresql_where=text("state <> 'done'")),
        Index("ix_run_waiting", "wait_until", postgresql_where=text("state = 'waiting'")),
        Index("ix_run_agent_id", "agent_id"),
        Index("ix_run_trigger_message_id", "trigger_message_id"),
        Index("ix_run_work_item_id", "work_item_id"),
        CheckConstraint(
            "trigger_message_id IS NOT NULL OR work_item_id IS NOT NULL", name="trigger"
        ),
        CheckConstraint(f"chain_depth BETWEEN 0 AND {MAX_CHAIN_DEPTH}", name="chain_depth"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent.id", ondelete="CASCADE"), nullable=False
    )
    # Who asked: whose rights the run reads with, who is billed (spec 5.4).
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    trigger_message_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("message.id", ondelete="CASCADE")
    )
    work_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("work_item.id", ondelete="CASCADE")
    )
    chain_depth: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    # The root of the channel thread a mention's run answers in: its lane. NULL: the
    # conversation is the lane (a DM, a page thread, a ticket thread).
    lane_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("message.id", ondelete="CASCADE")
    )
    state: Mapped[RunState] = mapped_column(String(16), nullable=False)
    stop_reason: Mapped[StopReason | None] = mapped_column(String(32))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recoveries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    wait_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunEvent(UuidPk, OrgScoped, Base):
    __tablename__ = "run_event"
    __table_args__ = (
        CheckConstraint(_in("kind", EventKind), name="kind"),
        Index("uq_run_event_step", "run_id", "attempt", "seq", unique=True),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("run.id", ondelete="CASCADE"), nullable=False
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[EventKind] = mapped_column(String(16), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class RunCancelRequest(OrgScoped, Base):
    """Someone asked the run to stop: once per run, before it is done."""

    __tablename__ = "run_cancel_request"

    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("run.id", ondelete="CASCADE"), primary_key=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )


class RateWindow(OrgScoped, Base):
    """`requests_per_minute` of a connection, across workers: the calls started in the
    current window (spec 12.4: no such state in memory)."""

    __tablename__ = "ai_rate_window"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_connection.id", ondelete="CASCADE"), primary_key=True
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calls: Mapped[int] = mapped_column(Integer, nullable=False)
