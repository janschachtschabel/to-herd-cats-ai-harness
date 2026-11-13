"""The event outbox (spec 4.3): every service method that changes something writes an
event in its own transaction with `emit`; the worker's dispatcher hands each event to
the handlers registered for its type (`app.worker`).

- `emit` adds the row and calls `NOTIFY herd_outbox`, which Postgres delivers when the
  caller's transaction commits (never for a rolled-back one), waking the dispatchers.
- `event_delivery` records which handler has had which event. A handler's effect and
  its record are written in one transaction, so an effect is committed exactly once
  even when the event is handed over again (at least once).
- Payloads hold ids and flags, never message text or other content: events travel to
  handlers and from there into `NOTIFY` payloads; nothing of them is logged.
"""

import uuid
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
    """One event. Pending while neither `dispatched_at` nor `failed_at` is set; then
    due at `next_attempt_at`, and `attempts` counts the passes in which a handler
    failed."""

    __tablename__ = "event_outbox"
    __table_args__ = (
        Index(
            "ix_event_outbox_due",
            "next_attempt_at",
            postgresql_where=text("dispatched_at IS NULL AND failed_at IS NULL"),
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
    event = EventOutbox(
        org_id=actor.org_id,
        type=type,
        actor_type=actor.principal.type,
        actor_id=actor.principal.id,
        space_id=space_id,
        subject_type=subject_type,
        subject_id=subject_id,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    await session.execute(select(func.pg_notify(OUTBOX_CHANNEL, "")))
    return event
