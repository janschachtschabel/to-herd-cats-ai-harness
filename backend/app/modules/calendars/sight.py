"""Who sees an event, and how much (plan M10 decision 3): the one rule.

- `FULL`: its organiser and its attendees (of that row: an override has attendees of
  its own), whatever space it lies in (an actor with a read scope, a run: only inside
  it, as `core/access.py` holds it); an
  admin on the named way (the call names the space or the event and went through
  `access.require`, which audits a foreign team or personal space; E4); and, for an
  event that is not private, whoever reads its calendar's space. A `FULL` that comes
  from admin power alone (`by_admin_power`: a private event of someone else, a member
  admin and an open space included) is audited by the caller, one
  `calendar.private_read` per admin, event and UTC day.
- `BUSY`: anyone else who reads the calendar's space, for a private event: times and
  "busy", never its title, place, text, UID or organiser (`redacted`).
- `NONE`: everyone else; such an event answers like an unknown id.

"Reads" comes from the lists' rule (`access.member_space_ids`: never by admin power)
unless the call is the named way. "Attends" (organises or is invited to the row)
needs the database: it is SQL alone (`attends_sql`), read as a column beside the row
(`EventRepository.find`, `in_window`, `attended`). `listed_events_sql` is the lists'
rule as SQL: the events of member spaces and those one attends. `full_sql` is the rule
for `FULL` as SQL, for filters that must not answer by hidden content (the title
search).
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import ColumnElement, and_, or_, select, true

from app.core.access import member_space_ids, visible_space_ids
from app.core.actor import Actor
from app.core.permissions import ADMIN_ROLES
from app.modules.calendars.attendee_models import CalendarEventAttendee
from app.modules.calendars.event_models import CalendarEvent, EventVisibility


class Sight(StrEnum):
    FULL = "full"
    BUSY = "busy"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class Seen:
    """An event, how much of it the caller sees (`events.EventService.get`), and
    whether the caller attends it (organises it or is invited to it)."""

    event: CalendarEvent
    sight: Sight
    attends: bool = False


def admin_power(actor: Actor) -> bool:
    """Admin power over content: an admin acting for herself (a run's scope caps it)."""
    return actor.system_role in ADMIN_ROLES and actor.read_scope is None


def organises(actor: Actor, event: CalendarEvent) -> bool:
    """Whether the actor is the event's organiser (who alone, besides an admin on the
    named way, changes its visibility; task 3b)."""
    return event.organizer_type == actor.principal.type and event.organizer_id == actor.principal.id


def of(actor: Actor, event: CalendarEvent, *, reads: bool, attends: bool, named: bool) -> Sight:
    """`reads`: the actor reads the event's space (lists: as a member; named: through
    `access.require`); `attends`: it organises the event or is invited to it
    (`attends_sql`); `named`: the call is the named way, the only one on which admin
    power counts."""
    if attends or (named and reads and admin_power(actor)):
        return Sight.FULL
    if not reads:
        return Sight.NONE
    return Sight.FULL if event.visibility == EventVisibility.DEFAULT else Sight.BUSY


def by_admin_power(
    actor: Actor, event: CalendarEvent, *, reads: bool, attends: bool, named: bool
) -> bool:
    """Whether `of` gives `FULL` only by admin power (it would give less without):
    such a read is audited (`calendar.private_read`, review M10 task 3a R3a-4)."""
    full = of(actor, event, reads=reads, attends=attends, named=named) is Sight.FULL
    return full and of(actor, event, reads=reads, attends=attends, named=False) is not Sight.FULL


def attends_sql(actor: Actor) -> ColumnElement[bool]:
    """Whether the actor organises the event row or is invited to it, inside its read
    scope if it has one (a run sees no event outside its scope, attended or not)."""
    invited = select(CalendarEventAttendee.event_id).where(
        CalendarEventAttendee.org_id == actor.org_id,
        CalendarEventAttendee.principal_type == actor.principal.type,
        CalendarEventAttendee.principal_id == actor.principal.id,
    )
    clause = or_(
        and_(
            CalendarEvent.organizer_type == actor.principal.type,
            CalendarEvent.organizer_id == actor.principal.id,
        ),
        CalendarEvent.id.in_(invited),
    )
    if actor.read_scope is not None:
        clause = and_(clause, CalendarEvent.space_id.in_(actor.read_scope.ids()))
    return clause


def reads_sql(actor: Actor) -> ColumnElement[bool]:
    """Whether the actor reads the event's space by the lists' rule."""
    return CalendarEvent.space_id.in_(member_space_ids(actor))


def listed_events_sql(actor: Actor) -> ColumnElement[bool]:
    """The lists' rule (decision 3, C1): events of the spaces the actor belongs to (or
    open ones its role reads) and events it attends; never by admin power."""
    return or_(reads_sql(actor), attends_sql(actor))


def named_events_sql(space_id: uuid.UUID) -> ColumnElement[bool]:
    """The named way: the events of the one space the call named (after `require`)."""
    return CalendarEvent.space_id == space_id


def window_sql(
    actor: Actor, *, space_id: uuid.UUID | None, mine: bool
) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    """(rule, reads) of a window: the named space's events, all read (after `require`),
    or the lists' rule with `reads_sql` per row; `mine` keeps what the actor attends."""
    rule = listed_events_sql(actor) if space_id is None else named_events_sql(space_id)
    reads: ColumnElement[bool] = reads_sql(actor) if space_id is None else true()
    return (and_(rule, attends_sql(actor)) if mine else rule), reads


def by_id_sql(actor: Actor) -> ColumnElement[bool]:
    """The events an id may find, before `access.require` decides on the space: those
    of spaces the actor may read (admin power included) and those it attends; any
    other answers like an unknown id, in the same one statement."""
    return or_(CalendarEvent.space_id.in_(visible_space_ids(actor)), attends_sql(actor))


def full_sql(actor: Actor, *, named: bool) -> ColumnElement[bool]:
    """`of(...) == FULL` as SQL, for events that already pass the call's rule (one it
    does not read it passes only as its organiser)."""
    if named and admin_power(actor):
        return true()
    return or_(attends_sql(actor), CalendarEvent.visibility == EventVisibility.DEFAULT)
