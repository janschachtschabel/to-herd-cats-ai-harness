"""Attendees (plan M10 decisions 5 and 7): rows on an event, never copies of it.

- An attendee is a principal of the system (`user` or `agent`) **or** an address with
  a display name (`email`, `name`): never both. A person's address is never stored
  here (people must not learn addresses through events).
- `role`: `required` or `optional`; `response`: `needs_action`, `accepted`,
  `tentative` or `declined`. An agent is accepted from the start and starts nothing.
- At most `MAX_ATTENDEES` per event; one row per principal and per address (letter
  case aside) on an event.
- A row belongs to one event row: an override has rows of its own (a copy of its
  series' when it is made), and the part a split makes takes copies along. They go
  with the event (foreign key, `ON DELETE CASCADE`); a tombstone keeps them, so its
  attendees still read what became of it.
"""

import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk
from app.core.principal import PrincipalType

MAX_ATTENDEES = 100
EMAIL_MAX = 320
NAME_MAX = 200


class AttendeeRole(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class Response(StrEnum):
    NEEDS_ACTION = "needs_action"
    ACCEPTED = "accepted"
    TENTATIVE = "tentative"
    DECLINED = "declined"


def _values(kind: type[StrEnum]) -> str:
    return ", ".join(f"'{v.value}'" for v in kind)


class CalendarEventAttendee(UuidPk, OrgScoped, Base):
    __tablename__ = "calendar_event_attendee"
    __table_args__ = (
        CheckConstraint("principal_type IN ('user', 'agent')", name="principal_type"),
        CheckConstraint(
            "(principal_type IS NULL) = (principal_id IS NULL)"
            " AND (principal_id IS NULL) = (email IS NOT NULL)",
            name="who",
        ),
        CheckConstraint(f"role IN ({_values(AttendeeRole)})", name="role"),
        CheckConstraint(f"response IN ({_values(Response)})", name="response"),
        Index(
            "uq_calendar_event_attendee_principal",
            "event_id",
            "principal_type",
            "principal_id",
            unique=True,
            postgresql_where=text("principal_id IS NOT NULL"),
        ),
        Index(
            "uq_calendar_event_attendee_email",
            "event_id",
            func.lower(text("email")),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        # What a person attends ("my events", sight): by principal, then event.
        Index(
            "ix_calendar_event_attendee_principal",
            "principal_id",
            "event_id",
            postgresql_where=text("principal_id IS NOT NULL"),
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("calendar_event.id", ondelete="CASCADE"),
        nullable=False,
    )
    principal_type: Mapped[PrincipalType | None] = mapped_column(String(16))
    principal_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    email: Mapped[str | None] = mapped_column(String(EMAIL_MAX))
    # An address's display name (empty for a principal: its name comes from it).
    name: Mapped[str] = mapped_column(
        String(NAME_MAX), nullable=False, default="", server_default=""
    )
    role: Mapped[AttendeeRole] = mapped_column(
        String(16), nullable=False, default=AttendeeRole.REQUIRED
    )
    response: Mapped[Response] = mapped_column(
        String(16), nullable=False, default=Response.NEEDS_ACTION
    )
