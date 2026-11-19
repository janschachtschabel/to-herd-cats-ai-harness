"""An event's attendee list as a client sets it (plan M10 task 4): what to add, take
off and change, compared by who an attendee is (a principal, or an address with its
letter case aside). Pure: the service checks rights and stores it."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.core.errors import ValidationFailed
from app.core.principal import Principal, PrincipalType
from app.modules.calendars.attendee_models import (
    MAX_ATTENDEES,
    AttendeeRole,
    CalendarEventAttendee,
    Response,
)

type Key = tuple[str, str]


class Kind(StrEnum):
    USER = "user"
    AGENT = "agent"
    EMAIL = "email"


class Delivery(StrEnum):
    """How an invitation reaches its attendee: `internal` (a person or agent of the
    system: the activity view), `not_sent` (an address: nothing sends it; the `.ics`
    file is for passing on), `provider` (an address a linked Google calendar sends to:
    plan M10 task 16)."""

    INTERNAL = "internal"
    NOT_SENT = "not_sent"
    PROVIDER = "provider"


@dataclass(frozen=True, slots=True)
class Invitee:
    kind: Kind
    id: uuid.UUID | None = None
    email: str | None = None
    name: str = ""
    role: AttendeeRole = AttendeeRole.REQUIRED

    @property
    def key(self) -> Key:
        return (
            self.kind.value,
            (self.email or "").lower() if self.kind is Kind.EMAIL else str(self.id),
        )

    @property
    def principal(self) -> Principal | None:
        if self.kind is Kind.EMAIL or self.id is None:
            return None
        return Principal(PrincipalType(self.kind.value), self.id)


def key_of(attendee: CalendarEventAttendee) -> Key:
    if attendee.principal_type is None:
        return (Kind.EMAIL.value, (attendee.email or "").lower())
    return (str(attendee.principal_type), str(attendee.principal_id))


def delivery_of(attendee: CalendarEventAttendee) -> Delivery:
    """How the attendee hears of the event (`provider` comes with task 16)."""
    return Delivery.INTERNAL if attendee.principal_type is not None else Delivery.NOT_SENT


@dataclass(frozen=True, slots=True)
class Diff:
    added: list[Invitee] = field(default_factory=list)
    removed: list[CalendarEventAttendee] = field(default_factory=list)
    changed: list[tuple[CalendarEventAttendee, Invitee]] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


def too_many() -> ValidationFailed:
    return ValidationFailed("At most 100 attendees", code="event.too_many_attendees")


def diff(current: Sequence[CalendarEventAttendee], wanted: Sequence[Invitee]) -> Diff:
    """From `current` to `wanted` (422 `event.attendee_duplicate` for one named twice,
    `event.too_many_attendees` beyond 100)."""
    if len(wanted) > MAX_ATTENDEES:
        raise too_many()
    by_key = {invitee.key: invitee for invitee in wanted}
    if len(by_key) != len(wanted):
        raise ValidationFailed("An attendee is named twice", code="event.attendee_duplicate")
    have = {key_of(attendee): attendee for attendee in current}
    changed = [
        (have[key], invitee)
        for key, invitee in by_key.items()
        if key in have and (have[key].role, _name(have[key])) != (invitee.role, _name(invitee))
    ]
    return Diff(
        added=[invitee for key, invitee in by_key.items() if key not in have],
        removed=[attendee for key, attendee in have.items() if key not in by_key],
        changed=changed,
    )


def _name(who: CalendarEventAttendee | Invitee) -> str:
    """An address's display name (a principal's comes from it, never stored)."""
    return who.name if who.email is not None else ""


def new_row(org_id: uuid.UUID, event_id: uuid.UUID, invitee: Invitee) -> CalendarEventAttendee:
    """The row of a new attendee: an agent is accepted from the start."""
    principal = invitee.principal
    return CalendarEventAttendee(
        org_id=org_id,
        event_id=event_id,
        principal_type=principal.type if principal else None,
        principal_id=principal.id if principal else None,
        email=invitee.email if principal is None else None,
        name=_name(invitee),
        role=invitee.role,
        response=Response.ACCEPTED if invitee.kind is Kind.AGENT else Response.NEEDS_ACTION,
    )


def change_row(attendee: CalendarEventAttendee, invitee: Invitee) -> None:
    attendee.role = invitee.role
    attendee.name = _name(invitee)
