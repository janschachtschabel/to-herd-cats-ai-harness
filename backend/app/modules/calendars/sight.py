"""Who sees an event, and how much (plan M10 decision 3): the one rule.

- `FULL`: its organiser (task 4: and its attendees), whatever space it lies in; an
  admin on the named way (the call names the space or the event and went through
  `access.require`, which audits a foreign team or personal space; E4); and, for an
  event that is not private, whoever reads its calendar's space.
- `BUSY`: anyone else who reads the calendar's space, for a private event: times and
  "busy", never its title, place, text, UID or organiser (`redacted`).
- `NONE`: everyone else; such an event answers like an unknown id.

"Reads" comes from the lists' rule (`access.member_space_ids`: never by admin power)
unless the call is the named way. `listed_events_sql` is the lists' rule as SQL: the
events of member spaces and those one organises. `full_sql` is the rule for `FULL` as
SQL, for filters that must not answer by hidden content (the title search).
"""

import uuid
from enum import StrEnum

from sqlalchemy import ColumnElement, and_, or_, true

from app.core.access import member_space_ids
from app.core.actor import Actor
from app.core.permissions import ADMIN_ROLES
from app.modules.calendars.event_models import CalendarEvent, EventVisibility


class Sight(StrEnum):
    FULL = "full"
    BUSY = "busy"
    NONE = "none"


def _admin(actor: Actor) -> bool:
    """Admin power over content: an admin acting for herself (a run's scope caps it)."""
    return actor.system_role in ADMIN_ROLES and actor.read_scope is None


def of(actor: Actor, event: CalendarEvent, *, reads: bool, attends: bool, named: bool) -> Sight:
    """`reads`: the actor reads the event's space (lists: as a member; named: through
    `access.require`); `attends`: it organises the event (task 4: or is invited);
    `named`: the call is the named way, the only one on which admin power counts."""
    if attends or (named and reads and _admin(actor)):
        return Sight.FULL
    if not reads:
        return Sight.NONE
    return Sight.FULL if event.visibility == EventVisibility.DEFAULT else Sight.BUSY


def attends(actor: Actor, event: CalendarEvent) -> bool:
    return event.organizer_type == actor.principal.type and event.organizer_id == actor.principal.id


def attends_sql(actor: Actor) -> ColumnElement[bool]:
    """`attends` as SQL."""
    return and_(
        CalendarEvent.organizer_type == actor.principal.type,
        CalendarEvent.organizer_id == actor.principal.id,
    )


def reads_sql(actor: Actor) -> ColumnElement[bool]:
    """Whether the actor reads the event's space by the lists' rule."""
    return CalendarEvent.space_id.in_(member_space_ids(actor))


def listed_events_sql(actor: Actor) -> ColumnElement[bool]:
    """The lists' rule (decision 3, C1): events of the spaces the actor belongs to (or
    open ones its role reads) and events it organises; never by admin power."""
    return or_(reads_sql(actor), attends_sql(actor))


def named_events_sql(space_id: uuid.UUID) -> ColumnElement[bool]:
    """The named way: the events of the one space the call named (after `require`)."""
    return CalendarEvent.space_id == space_id


def full_sql(actor: Actor, *, named: bool) -> ColumnElement[bool]:
    """`of(...) == FULL` as SQL, for events that already pass the call's rule (one it
    does not read it passes only as its organiser)."""
    if named and _admin(actor):
        return true()
    return or_(attends_sql(actor), CalendarEvent.visibility == EventVisibility.DEFAULT)
