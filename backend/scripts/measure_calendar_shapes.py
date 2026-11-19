"""What the calendar's expansion measurement asks (plan M10 Task 3c): the windows it
rotates over (weeks, month grids, spans for availability, around the anchor in
Europe/Berlin) and the availability load shape (`busy_times`)."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calendars import expansion, zones
from app.modules.calendars.event_models import CalendarEvent, EventStatus
from app.modules.calendars.event_repository import EventRepository
from scripts.measure_calendar_events import ANCHOR, ZONE

WINDOWS = 10


def _midnight(day: datetime) -> datetime:
    return zones.localise(datetime(day.year, day.month, day.day), ZONE)


def weeks() -> list[tuple[datetime, datetime]]:
    mondays = [ANCHOR + timedelta(weeks=w) for w in range(-4, WINDOWS - 4)]
    return [(_midnight(m), _midnight(m + timedelta(days=7))) for m in mondays]


def month_grids() -> list[tuple[datetime, datetime]]:
    """A month view's grid: six weeks from the Monday on or before the 1st."""
    grids = []
    for offset in range(-4, WINDOWS - 4):
        index = ANCHOR.year * 12 + ANCHOR.month - 1 + offset
        first = datetime(index // 12, index % 12 + 1, 1)
        monday = first - timedelta(days=first.weekday())
        grids.append((_midnight(monday), _midnight(monday + timedelta(days=42))))
    return grids


def spans(days: int) -> list[tuple[datetime, datetime]]:
    starts = [ANCHOR + timedelta(days=3 * d) for d in range(-5, WINDOWS - 5)]
    return [(_midnight(s), _midnight(s + timedelta(days=days))) for s in starts]


async def busy_times(
    session: AsyncSession, org_id: Any, people: dict[Any, Any], start: datetime, end: datetime
) -> tuple[dict[Any, list[tuple[datetime, datetime]]], list[expansion.Budget]]:
    """The availability load shape (decision 4, Task 5): the busy, not cancelled events of
    the people's personal calendars in one statement, the overrides of their series in a
    second, each person's expanded by `expansion.effective` with a budget of her own (in
    her zone), merged into sorted busy intervals. Occurrences are counted unmerged."""
    repo = EventRepository(session, org_id)
    rule = and_(
        CalendarEvent.space_id.in_(list(people)),
        CalendarEvent.busy.is_(True),
        CalendarEvent.status != EventStatus.CANCELLED,
    )
    limit = expansion.Budget().rows_allowed() * len(people) + 1
    rows = await repo.in_window(
        rule,
        true(),
        start,
        end,
        calendar_ids=None,
        title=None,
        full=true(),
        attends=true(),
        limit=limit,
    )
    taken = await repo.overridden([e.id for e, _, _ in rows if e.recurring])
    by_person: dict[Any, list[CalendarEvent]] = {}
    for event_row, _, _ in rows:
        by_person.setdefault(people[event_row.space_id], []).append(event_row)
    busy: dict[Any, list[tuple[datetime, datetime]]] = {}
    budgets = []
    for person, events in by_person.items():
        budget = expansion.Budget()
        found = expansion.effective(events, taken, start, end, viewer_zone=ZONE, budget=budget)
        budgets.append(budget)
        merged: list[tuple[datetime, datetime]] = []
        for o, _ in sorted(found, key=lambda f: f[0].start):
            if merged and o.start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], o.end))
            else:
                merged.append((o.start, o.end))
        busy[person] = merged
    return busy, budgets
