"""The events an event rule took in (plan M7 decisions 8 and 9): one row per rule and
event (the key, so an event handed over again is taken in once), with what the run
may be told of it (`subject_id`, the object it is about, and `ids`, the ids of its
payload: never content) and the chain's depth a run for it would have (`depth`).

A row waits (`firing_id` empty) while the rule's quiet time lasts; the term that
takes it (a run, or why none) names it. The run is told the event's kind, the ids of
the objects and how many events its term took (`runs.assignment`); a rule never
reacts to an event its own run caused on an object that run was about (`subject_id`
of the rows of that run's term).
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, SmallInteger, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped


class AutomationEvent(OrgScoped, Base):
    __tablename__ = "automation_event"
    __table_args__ = (
        Index(
            "ix_automation_event_waiting",
            "automation_id",
            postgresql_where=text("firing_id IS NULL"),
        ),
        Index("ix_automation_event_firing_id", "firing_id"),
    )

    automation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("automation.id", ondelete="CASCADE"), primary_key=True
    )
    # No foreign key: an event outlives what it is about, and this row outlives it.
    event_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    ids: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    firing_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("automation_firing.id", ondelete="CASCADE")
    )
