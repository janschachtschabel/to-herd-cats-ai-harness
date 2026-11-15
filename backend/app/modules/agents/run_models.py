"""Runs of agents and their journal (spec 8.1, 8.3; plan M6 decision 1; split from
`models.py`, which holds the agents).

`run`: one answer to a direct message, to a mention of the agent in a channel or a
thread (it answers in the mentioning message's thread), to a ticket assigned to it
(`work_item_id`: its task; it answers in the ticket's thread, `triggers.py`), or the
work of an automation that came due (`automation_id`; its lane is the automation,
plan M7). Created
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
conversation a run answers ends there, whatever take-up works on it. `taken_at` is the
current take-up (set by every claim): a take-up older than any run may run is stuck
(`gauge_repository`), however long the run waited before it.

`run_event`: the run's journal (plan M6 decision 1), one continuous sequence (`seq`,
counted on across take-ups; `attempt` notes the take-up that wrote it; the stop is
`seq` 0): model calls with their answer and usage, tool calls with their full
arguments and results, the stop. A run taken up again replays it and goes on after
its last step. Content lives only here, never in logs or metrics; readable by the
person who asked, the person responsible and those with `agent.manage`.

`run_cancel_request` and `ai_rate_window`: `run_control_models.py`.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow

# A tool's step (`step_host`): its lock waits and each statement end after so long.
STEP_LOCK_TIMEOUT_SECONDS = 5.0
STEP_STATEMENT_TIMEOUT_SECONDS = 20.0
# A person's request that asks a run to stop (a ticket taken away) waits for the run's
# row at most so long, then answers 409 `conflict.retry` (review M6 2, finding 4); less
# than Postgres' `deadlock_timeout` (1 s), so it loses a deadlock before detection.
REASSIGN_LOCK_TIMEOUT_SECONDS = 0.5
MAX_CHAIN_DEPTH = 3  # handovers from agent to agent that led to a run (plan M6 task 8)
MAX_HANDOVERS_PER_RUN = 5  # tickets one run hands to agents (review M6 finding 16c)


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
    BUDGET = "budget"  # a daily budget is reached (plan M7 decision 10)


class EventKind(StrEnum):
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    STOP = "stop"


# Where "one open run" counts: a channel thread's root (`Run.lane_id`), else the
# conversation.
LANE = text("COALESCE(lane_id, conversation_id)")


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


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
        Index("ix_run_automation_id", "automation_id"),
        CheckConstraint(
            "trigger_message_id IS NOT NULL OR work_item_id IS NOT NULL "
            "OR automation_id IS NOT NULL",
            name="trigger",
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
    # The automation that fired the run (plan M7; `modules/automations`).
    automation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("automation.id", ondelete="CASCADE")
    )
    # The lane, where one run is open at a time: the root of the channel thread a
    # mention's run answers in, or the automation that fired the run (its runs never
    # overlap, whatever their place). NULL: the conversation is the lane (a DM, a page
    # thread, a ticket thread). No foreign key: it names a message or an automation.
    lane_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
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
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
