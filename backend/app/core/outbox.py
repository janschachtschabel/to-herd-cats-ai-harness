"""The event outbox (spec 4.3): every service method that changes something writes an
event in its own transaction with `emit`; the worker's dispatcher hands each event to
the handlers registered for its type (`app.worker`).

- `emit` adds the row (`emit_many` several, in one INSERT) and calls `NOTIFY
  herd_outbox`, which Postgres delivers when the caller's transaction commits (never
  for a rolled-back one), waking the dispatchers.
  Inside `one_notify` (a worker's lane batch) the NOTIFY is sent once at its end.
- The worker routes each new event into one `event_lane` row per handler that wants
  it (`routed_at`); each handler works off its own lane (`app/worker/dispatcher.py`).
- `event_delivery` records which handler has had which event. A handler's effect and
  its record are written in one transaction, so an effect is committed exactly once
  even when the event is handed over again (at least once).
- Payloads hold ids and flags, never message text or other content: events travel to
  handlers and from there into `NOTIFY` payloads; nothing of them is logged.
"""

import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow
from app.core.principal import Principal, PrincipalType

OUTBOX_CHANNEL = "herd_outbox"
MAX_TYPE_CHARS = 64
MAX_HANDLER_CHARS = 100


class EventOutbox(UuidPk, OrgScoped, Base):
    """One event. Pending while neither `dispatched_at` nor `failed_at` is set; routed
    (`routed_at`) once its lanes are written; dispatched when no lane is left, failed
    when only lanes that gave up are left.

    `attempts` and `next_attempt_at` belong to the dispatcher of M4 (one pass over all
    handlers): this release neither reads nor writes them (retries are counted per
    lane), its predecessor's workers still do while both run during an update. They
    and `ix_event_outbox_due` are dropped in the next release (expand, then
    contract)."""

    __tablename__ = "event_outbox"
    __table_args__ = (
        Index(
            "ix_event_outbox_due",
            "next_attempt_at",
            postgresql_where=text("dispatched_at IS NULL AND failed_at IS NULL"),
        ),
        Index(
            "ix_event_outbox_unrouted",
            "id",
            postgresql_where=text(
                "routed_at IS NULL AND dispatched_at IS NULL AND failed_at IS NULL"
            ),
        ),
        Index(
            "ix_event_outbox_dispatched_at",
            "dispatched_at",
            postgresql_where=text("dispatched_at IS NOT NULL"),
        ),
        Index(
            "ix_event_outbox_failed",
            "failed_at",
            postgresql_where=text("failed_at IS NOT NULL"),
        ),
    )

    type: Mapped[str] = mapped_column(String(MAX_TYPE_CHARS), nullable=False)
    actor_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # No foreign keys to the subject or its space: an event outlives what it is about.
    space_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    routed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventLane(Base):
    """An event waiting for one handler: removed when the handler has had it, kept with
    `failed_at` when the handler gave up. `attempts` counts the handler's failed tries
    of it, and it is due again at `next_attempt_at`."""

    __tablename__ = "event_lane"
    __table_args__ = (
        Index(
            "ix_event_lane_due", "handler", "event_id", postgresql_where=text("failed_at IS NULL")
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("event_outbox.id", ondelete="CASCADE"),
        primary_key=True,
    )
    handler: Mapped[str] = mapped_column(String(MAX_HANDLER_CHARS), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventDelivery(Base):
    """A handler has had the event; written in the handler's transaction."""

    __tablename__ = "event_delivery"

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("event_outbox.id", ondelete="CASCADE"),
        primary_key=True,
    )
    handler: Mapped[str] = mapped_column(String(MAX_HANDLER_CHARS), primary_key=True)


class Acting(Protocol):
    """Who caused an event: an `Actor`, or an `EventActor` (a handler acting on behalf
    of the event it handles)."""

    @property
    def org_id(self) -> uuid.UUID: ...

    @property
    def principal(self) -> Principal: ...


@dataclass(frozen=True, slots=True)
class EventActor:
    org_id: uuid.UUID
    principal: Principal


@dataclass(frozen=True, slots=True)
class Event:
    """An event as handlers get it."""

    id: uuid.UUID
    org_id: uuid.UUID
    type: str
    actor: Principal
    space_id: uuid.UUID | None
    subject_type: str
    subject_id: uuid.UUID
    payload: dict[str, Any]
    created_at: datetime

    @property
    def acting(self) -> EventActor:
        """The event's cause, for events a handler emits in turn."""
        return EventActor(self.org_id, self.actor)

    @classmethod
    def of(cls, row: EventOutbox) -> "Event":
        return cls(
            id=row.id,
            org_id=row.org_id,
            type=row.type,
            actor=Principal(PrincipalType(row.actor_type), row.actor_id),
            space_id=row.space_id,
            subject_type=row.subject_type,
            subject_id=row.subject_id,
            payload=dict(row.payload),
            created_at=row.created_at,
        )


# Set inside `one_notify`: whether an event was written there (emit's NOTIFY waits).
_deferred: ContextVar[list[bool] | None] = ContextVar("herd_outbox_deferred", default=None)


async def _notify(session: AsyncSession) -> None:
    await session.execute(select(func.pg_notify(OUTBOX_CHANNEL, "")))


@asynccontextmanager
async def one_notify(session: AsyncSession) -> AsyncIterator[None]:
    """Within the block (one task, one transaction), `emit` sends no NOTIFY of its own;
    one is sent at the end if an event was written. Postgres folds equal NOTIFYs of a
    transaction into one anyway; this saves the statements (review M4 P3). Without an
    error only: a failed block's transaction is rolled back, and its events with it."""
    token = _deferred.set([])
    try:
        yield
        emitted = bool(_deferred.get())
    finally:
        _deferred.reset(token)
    if emitted:
        await _notify(session)


@dataclass(frozen=True, slots=True)
class NewEvent:
    """An event to write with `emit_many` (all of one actor)."""

    type: str
    space_id: uuid.UUID | None
    subject_type: str
    subject_id: uuid.UUID
    payload: dict[str, Any]


async def emit(
    session: AsyncSession,
    *,
    type: str,
    actor: Acting,
    space_id: uuid.UUID | None,
    subject_type: str,
    subject_id: uuid.UUID,
    payload: dict[str, Any],
) -> EventOutbox:
    """Write an event in the caller's transaction (the caller commits)."""
    new = NewEvent(type, space_id, subject_type, subject_id, payload)
    (event,) = await emit_many(session, actor=actor, events=[new])
    return event


async def emit_many(
    session: AsyncSession, *, actor: Acting, events: Sequence[NewEvent]
) -> list[EventOutbox]:
    """Write events in the caller's transaction, as one multi-row INSERT and one
    NOTIFY (a sprint closed with many tickets: one event per ticket, module review
    M4b finding 6)."""
    if not events:
        return []
    rows = [
        EventOutbox(
            org_id=actor.org_id,
            type=new.type,
            actor_type=actor.principal.type,
            actor_id=actor.principal.id,
            space_id=new.space_id,
            subject_type=new.subject_type,
            subject_id=new.subject_id,
            payload=new.payload,
        )
        for new in events
    ]
    session.add_all(rows)
    await session.flush()
    deferred = _deferred.get()
    if deferred is None:
        await _notify(session)
    else:
        deferred.append(True)
    return rows
