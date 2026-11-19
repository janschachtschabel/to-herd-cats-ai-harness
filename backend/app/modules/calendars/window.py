"""The event window (plan M10 decision 6): every occurrence overlapping `[start, end)`
of the events the caller may list, by (start, event id), a page at a time.

- Which events: without `space_id` the lists' rule (`sight.listed_events_sql`: member
  spaces and what one organises; never by admin power, C1); with `space_id` the named
  way, through `access.require(calendar.read)` (an admin's look into a foreign team or
  personal space is audited), the events of that space alone. `mine`: only those the
  caller organises (task 4 adds those it is invited to). `query`: a title search among
  the events the caller sees in full, so hidden content answers nothing.
- One statement loads every event that can reach the window (`recurs_until`); series
  are expanded in Python (`recurrence.occurrences`), overrides take the place of their
  occurrence. All-day events float on their days: they are loaded 14 hours to either
  side and compared in the viewer's zone `viewer_zone` (default UTC), so a viewer in
  UTC+13 or UTC−11 sees the day's event and not the neighbours'.
- At most `MAX_OCCURRENCES` occurrences (and `MAX_CANDIDATES` events) per call;
  beyond, 422 `calendar.window_too_dense`, counted.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require
from app.core.errors import ValidationFailed
from app.core.pagination import PageParams, decode_cursor, encode_cursor
from app.modules.calendars import recurrence, sight, zones
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_repository import ALL_DAY_REACH, EventRepository
from app.modules.calendars.event_schemas import OccurrenceOut
from app.modules.calendars.event_times import floating_day, series_of
from app.modules.calendars.metrics import WINDOW_TOO_DENSE
from app.modules.calendars.recurrence import Occurrence
from app.modules.calendars.recurrence_series import bounded
from app.modules.calendars.sight import Sight

logger = logging.getLogger(__name__)

MAX_OCCURRENCES = recurrence.DEFAULT_LIMIT  # 2,000
MAX_CANDIDATES = 2 * MAX_OCCURRENCES
VIEWER_ZONE = "UTC"

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
    if end <= start:
        raise ValidationFailed(code="calendar.invalid_window")
    zone = viewer_zone or VIEWER_ZONE
    try:
        zones.zone(zone)
    except zones.ZoneUnknown:
        raise ValidationFailed(code="calendar.invalid_time_zone") from None
    after = decode_cursor(params.cursor) if params.cursor else None
    start, end = bounded(start), bounded(end)
    named = space_id is not None
    if space_id is not None:
        await require(session, actor, Action.CALENDAR_READ, space_id)
        rule: ColumnElement[bool] = sight.named_events_sql(space_id)
        reads: ColumnElement[bool] = true()
    else:
        rule, reads = sight.listed_events_sql(actor), sight.reads_sql(actor)
    if mine:
        rule = and_(rule, sight.attends_sql(actor))
    repo = EventRepository(session, actor.org_id)
    rows = await repo.in_window(
        rule,
        reads,
        start,
        end,
        calendar_ids=calendar_ids,
        title=query,
        full=sight.full_sql(actor, named=named),
        limit=MAX_CANDIDATES + 1,
    )
    if len(rows) > MAX_CANDIDATES:
        raise too_dense()
    taken = await repo.overridden([event.id for event, _ in rows if event.recurring])
    found: list[Found] = []
    for event, reading in rows:
        seen = sight.of(
            actor, event, reads=reading, attends=sight.attends(actor, event), named=named
        )
        if seen is Sight.NONE:
            continue
        for occurrence in _expand(event, start, end, zone, MAX_OCCURRENCES - len(found)):
            if not (event.recurring and (event.id, occurrence.recurrence_id) in taken):
                found.append((occurrence, event, seen))
    if len(found) > MAX_OCCURRENCES:
        raise too_dense()
    found.sort(key=lambda f: (f[0].start, f[1].id))
    if after is not None:
        found = [f for f in found if (f[0].start, f[1].id) > after]
    page = found[: params.limit]
    more = len(found) > params.limit
    return pagination.Page[OccurrenceOut](
        items=[OccurrenceOut.of(event, occurrence, seen) for occurrence, event, seen in page],
        next_cursor=encode_cursor(page[-1][0].start, page[-1][1].id) if more else None,
    )


def _expand(
    event: CalendarEvent, start: datetime, end: datetime, zone: str, room: int
) -> list[Occurrence]:
    """The event's occurrences in the window; all-day ones by the viewer's days."""
    try:
        series = series_of(event)
        if not event.all_day:
            return recurrence.occurrences(series, start, end, limit=room)
        near = recurrence.occurrences(
            series, start - ALL_DAY_REACH, end + ALL_DAY_REACH, limit=room
        )
    except recurrence.TooDense:
        raise too_dense() from None
    except (recurrence.SeriesInvalid, ValueError):
        logger.warning("calendar.series_unreadable", extra={"event_id": str(event.id)})
        return []
    return [
        o for o in near if floating_day(o.start, zone) < end and floating_day(o.end, zone) > start
    ]
