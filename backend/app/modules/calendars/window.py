"""The event window (plan M10 decision 6): every occurrence overlapping `[start, end)`
of the events the caller may list, by (start, event id), a page at a time.

- Which events: without `space_id` the lists' rule (`sight.listed_events_sql`: member
  spaces and what one organises; never by admin power, C1); with `space_id` the named
  way, through `access.require(calendar.read)` (an admin's look into a foreign team or
  personal space is audited), the events of that space alone. `mine`: only those the
  caller organises (task 4 adds those it is invited to). `query`: a title search among
  the events the caller sees in full, so hidden content answers nothing. The private
  events a page shows by admin power alone are audited (`calendar.private_read`).
- One statement loads every event that can reach the window (`recurs_until`), without
  its description; `expansion.effective` expands them (overrides take the place of
  their occurrence; all-day events by the viewer's days in `viewer_zone`, default UTC,
  so a viewer in UTC+13 or UTC−11 sees the day's event and not the neighbours').
- Its bounds lie in the years 1900 to 2399 as sent (422
  `calendar.window_out_of_range`), `from` before `to` (`calendar.invalid_window`).
- Paged by (start, event id); a cursor holds the viewer zone and is valid with it
  only (422 `calendar.cursor_time_zone`).
- At most 2,000 occurrences per call, and the expansion's counted work bounded
  (`expansion.Budget`: rows and rule candidates, so a calendar full of series that do
  not occur in the window stays readable); beyond, 422 `calendar.window_too_dense`,
  counted.
"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require
from app.core.errors import ValidationFailed
from app.core.pagination import PageParams, decode_tagged_cursor, encode_tagged_cursor
from app.modules.audit.recorder import record_private_event_reads
from app.modules.calendars import expansion, recurrence, sight, zones
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_repository import EventRepository
from app.modules.calendars.event_schemas import OccurrenceOut
from app.modules.calendars.metrics import WINDOW_TOO_DENSE
from app.modules.calendars.recurrence import Occurrence
from app.modules.calendars.recurrence_series import bounded
from app.modules.calendars.sight import Sight

MAX_OCCURRENCES = expansion.MAX_OCCURRENCES  # 2,000
VIEWER_ZONE = "UTC"
FIRST_WALL = datetime(recurrence.FIRST_YEAR, 1, 1)
LAST_WALL = datetime(recurrence.LAST_YEAR + 1, 1, 1)

type Found = tuple[Occurrence, CalendarEvent, Sight]


def too_dense() -> ValidationFailed:
    WINDOW_TOO_DENSE.inc()
    return ValidationFailed("Too many occurrences in the window", code="calendar.window_too_dense")


async def list_window(
    session: AsyncSession,
    actor: Actor,
    *,
    start: datetime,
    end: datetime,
    calendar_ids: list[uuid.UUID] | None,
    space_id: uuid.UUID | None,
    mine: bool,
    query: str | None,
    params: PageParams,
    viewer_zone: str | None = None,
) -> pagination.Page[OccurrenceOut]:
    if not (_in_years(start) and _in_years(end)):
        raise ValidationFailed(code="calendar.window_out_of_range")
    if end <= start:
        raise ValidationFailed(code="calendar.invalid_window")
    zone = viewer_zone or VIEWER_ZONE
    try:
        zones.zone(zone)
    except zones.ZoneUnknown:
        raise ValidationFailed(code="calendar.invalid_time_zone") from None
    after = _after(params.cursor, zone)
    start, end = bounded(start), bounded(end)
    named = space_id is not None
    if space_id is not None:
        await require(session, actor, Action.CALENDAR_READ, space_id)
    rule, reads = sight.window_sql(actor, space_id=space_id, mine=mine)
    repo = EventRepository(session, actor.org_id)
    budget = expansion.Budget()
    rows = await repo.in_window(
        rule,
        reads,
        start,
        end,
        calendar_ids=calendar_ids,
        title=query,
        full=sight.full_sql(actor, named=named),
        limit=budget.rows_allowed() + 1,
    )
    seen: dict[uuid.UUID, Sight] = {}
    reads_of = {event.id: reading for event, reading in rows}
    for event, reading in rows:
        found_sight = sight.of(
            actor, event, reads=reading, attends=sight.attends(actor, event), named=named
        )
        if found_sight is not Sight.NONE:
            seen[event.id] = found_sight
    shown = [event for event, _ in rows if event.id in seen]
    try:
        budget.charge(len(rows) - len(shown))
        taken = await repo.overridden([event.id for event in shown if event.recurring])
        expanded = expansion.effective(shown, taken, start, end, viewer_zone=zone, budget=budget)
    except expansion.TooDense:
        raise too_dense() from None
    found: list[Found] = [(occurrence, event, seen[event.id]) for occurrence, event in expanded]
    found.sort(key=lambda f: (f[0].start, f[1].id))
    if after is not None:
        found = [f for f in found if (f[0].start, f[1].id) > after]
    page = found[: params.limit]
    more = len(found) > params.limit
    shown_by_power = [
        (event.id, event.space_id, event.calendar_id)
        for _, event, event_sight in page
        if event_sight is Sight.FULL
        and sight.by_admin_power(
            actor,
            event,
            reads=reads_of[event.id],
            attends=sight.attends(actor, event),
            named=named,
        )
    ]
    if shown_by_power:
        await record_private_event_reads(session, actor, shown_by_power)
    return pagination.Page[OccurrenceOut](
        items=[OccurrenceOut.of(event, occurrence, seen) for occurrence, event, seen in page],
        next_cursor=encode_tagged_cursor(page[-1][0].start, page[-1][1].id, zone) if more else None,
    )


def _after(cursor: str | None, zone: str) -> tuple[datetime, uuid.UUID] | None:
    """Where the page starts: a cursor is valid only with the viewer zone it was made
    with, whose days decided which all-day events the earlier pages held."""
    if not cursor:
        return None
    start, event_id, made_in = decode_tagged_cursor(cursor)
    if made_in != zone:
        raise ValidationFailed(code="calendar.cursor_time_zone")
    return start, event_id


def _in_years(bound: datetime) -> bool:
    """Whether the aware `bound`, read in the offset it came with, lies in the years
    events may (1900 to 2399; the end of 2399 included as a window's end)."""
    return FIRST_WALL <= bound.replace(tzinfo=None) <= LAST_WALL
