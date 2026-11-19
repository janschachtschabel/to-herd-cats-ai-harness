"""What every write of an event shares (plan M10 task 3b, decision 3, C2).

- `require_writable`: writing needs **full sight** of the event (with "busy" sight
  every attempt is 403 `event.private`, before anything else is said about it) and
  `calendar.write` in its space (403 `auth.permission_denied`); `visibility` changes
  only its organiser or an admin acting for herself on the named way (every by-id write
  is that way; 403 `event.visibility_organiser_only`). Every later write path
  (attendees, import, agent tools) calls this one function.
- `require_version`: the version the client read, else 409 `event.version_conflict`
  with `current_version` (said only to someone who passed `require_writable`).
- `refusals_roll_back`: a write runs in a savepoint; a refusal (any `AppError`) rolls
  it back and raises. Nothing here commits: the caller owns the transaction (an HTTP
  request, an import, an agent's step; review M10 task 3b, R3b-5). What the audit
  recorded before a refusal (an admin's look into a foreign space,
  `space.admin_access`; a private event read by admin power) outlives the caller's
  rollback through `audit.kept` (review M10 task 1, R1-M2).
- A write by admin power alone (a private event of someone else, or `calendar.write`
  only through the admin role) is audited, one `calendar.admin_write` per write with
  ids, the scope and the changed fields' names.
- Outbox: `calendar_event.updated` (the changed fields' names), `calendar_event.deleted`
  and `calendar_event.created`, with ids only; a deleted event stays a tombstone
  (`deleted_at`) for 30 days (`core/retention.py`).
"""

from collections.abc import AsyncIterator, Iterable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.access import Action, held_by_admin_power, require
from app.core.actor import Actor
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.models_base import utcnow
from app.core.outbox import emit
from app.modules.audit.recorder import record_event_admin_write
from app.modules.calendars import sight
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.sight import Seen, Sight

UID_DOMAIN = "to-herd-cats-ai"
CREATED = "calendar_event.created"
UPDATED = "calendar_event.updated"
DELETED = "calendar_event.deleted"

CONTENT_FIELDS = ("title", "description", "location", "status", "visibility", "busy")
SERIES_FIELDS = ("rrule", "rdates", "exdates")
# The stored fields a change can touch, by which `calendar_event.updated` names it.
STORED_FIELDS = (
    *CONTENT_FIELDS,
    "all_day",
    "starts_at",
    "ends_at",
    "tzid",
    *SERIES_FIELDS,
)


class Scope(StrEnum):
    """Which occurrences of a series a write touches (decision 6): `this` one (an
    override, or an EXDATE when deleting), this and the `following` (a split), or
    `all` (the series row; the only scope of an event that is no series)."""

    THIS = "this"
    FOLLOWING = "following"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class Change:
    """What a client changes, by API name (`CONTENT_FIELDS` and
    `event_times.TIME_FIELDS`): only the fields it sent."""

    values: Mapping[str, Any] = field(default_factory=dict)

    def content(self) -> dict[str, Any]:
        return {name: self.values[name] for name in CONTENT_FIELDS if name in self.values}

    def names_series(self) -> bool:
        return any(name in self.values for name in SERIES_FIELDS)


def new_uid() -> str:
    """A UID for an event made here (a new event, the part a split makes)."""
    return f"{uuid7()}@{UID_DOMAIN}"


def private() -> Forbidden:
    return Forbidden(code="event.private")


async def require_writable(
    session: AsyncSession, actor: Actor, seen: Seen, *, changes_visibility: bool = False
) -> None:
    """Raises unless the actor may write the event it sees as `seen`."""
    event = seen.event
    if seen.sight is not Sight.FULL:
        raise private()
    try:
        await require(session, actor, Action.CALENDAR_WRITE, event.space_id)
    except (NotFound, Forbidden):
        raise Forbidden(code="auth.permission_denied") from None
    if changes_visibility and not (sight.organises(actor, event) or sight.admin_power(actor)):
        raise Forbidden(code="event.visibility_organiser_only")


def require_version(event: CalendarEvent, version: int) -> None:
    if event.version != version:
        raise Conflict(
            "The event changed meanwhile",
            code="event.version_conflict",
            details={"current_version": event.version},
        )


@asynccontextmanager
async def refusals_roll_back(session: AsyncSession) -> AsyncIterator[None]:
    """The write inside runs in a savepoint; a refusal rolls only it back and raises.
    It never commits (the caller's transaction is the caller's)."""
    async with session.begin_nested():
        yield


# The stored field each API name of a change writes (review M10 task 3b, R3b-11: one
# naming, the columns', in the audit and the outbox).
_STORED_NAME = {"first_day": "starts_at", "last_day": "ends_at", "time_zone": "tzid"}


def stored_names(values: Iterable[str]) -> list[str]:
    return sorted({_STORED_NAME.get(name, name) for name in values})


def snapshot(event: CalendarEvent) -> dict[str, Any]:
    return {name: getattr(event, name) for name in STORED_FIELDS}


def changed_fields(before: Mapping[str, Any], event: CalendarEvent) -> list[str]:
    return sorted(name for name, old in before.items() if getattr(event, name) != old)


def tombstone(event: CalendarEvent) -> None:
    event.deleted_at = utcnow()
    event.version += 1


async def announce(
    session: AsyncSession,
    actor: Actor,
    event: CalendarEvent,
    kind: str,
    fields: Iterable[str] | None = None,
    *,
    overrides: Iterable[CalendarEvent] = (),
) -> None:
    """The outbox event of a change: ids, for an update the fields' names, and for a
    series the ids of the overrides the change wrote too (moved, re-homed, changed or
    made tombstones; review M10 task 3b, R3b-12)."""
    payload: dict[str, Any] = {"calendar_id": str(event.calendar_id)}
    if kind == UPDATED:
        payload["fields"] = sorted(fields or ())
    touched = sorted({str(override.id) for override in overrides})
    if touched:
        payload["overrides"] = touched
    await emit(
        session,
        type=kind,
        actor=actor,
        space_id=event.space_id,
        subject_type="calendar_event",
        subject_id=event.id,
        payload=payload,
    )


async def audit_admin_write(
    session: AsyncSession,
    actor: Actor,
    seen: Seen,
    *,
    change: str,
    scope: Scope,
    fields: Iterable[str],
    overrides_by_power: bool = False,
) -> None:
    """One `calendar.admin_write` if the write needed admin power: full sight of a
    private event of someone else (the event, or an override the write reached:
    `overrides_by_power`), or `calendar.write` only through the admin role."""
    event = seen.event
    attends = sight.attends(actor, event)
    by_power = (
        overrides_by_power
        or sight.by_admin_power(actor, event, reads=True, attends=attends, named=True)
        or await held_by_admin_power(session, actor, Action.CALENDAR_WRITE, event.space_id)
    )
    if by_power:
        await record_event_admin_write(
            session,
            actor,
            (event.id, event.space_id, event.calendar_id),
            change=change,
            scope=scope.value,
            fields=fields,
        )
