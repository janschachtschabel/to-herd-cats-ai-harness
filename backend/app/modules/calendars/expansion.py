"""The effective occurrences of stored events (plan M10 decision 6): one function for
every reader that expands events, the window (task 3a), free/busy (5), reminders (6)
and feeds (8a). Pure: no database, no sight.

Contract of `effective(rows, taken, start, end, *, viewer_zone, budget)`:

- In: live event rows (masters and overrides) the caller may expand, already filtered
  by its rule and its sight; `taken`, the (series id, recurrence id) of every live
  override of those series (`EventRepository.overridden`); a window `[start, end)`;
  the zone whose days all-day events are compared by; a `Budget`.
- Out: (occurrence, event) for every occurrence overlapping the window, unordered:
  a series in its zone's wall time (`event_times.series_of`, `recurrence.occurrences`),
  without its EXDATEs and without each occurrence an override took (wherever the
  override moved); an override row as a single event at its own time; an all-day
  event (floating on 00:00 UTC) when its days meet the window's in `viewer_zone`
  (loaded within `event_repository.ALL_DAY_REACH`, so 14 hours to either side).
- Bounded: `TooDense` beyond `budget.occurrences` occurrences, or once the counted
  work passes `budget.work`: each row costs `ROW_WORK`, each candidate a rule
  generates one (`recurrence_jump.Counter`; endless series jump to the window, a
  counted one runs from its start). A row whose stored series no longer reads (a zone
  `tzdata` dropped) is logged by id and skipped.
"""

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from app.modules.calendars import recurrence
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_repository import ALL_DAY_REACH
from app.modules.calendars.event_times import floating_day, series_of
from app.modules.calendars.recurrence import Occurrence, TooDense
from app.modules.calendars.recurrence_jump import Counter

__all__ = ["MAX_OCCURRENCES", "MAX_WORK", "ROW_WORK", "Budget", "TooDense", "effective"]

logger = logging.getLogger(__name__)

MAX_OCCURRENCES = recurrence.DEFAULT_LIMIT  # 2,000 (decision 6)
# Counted work per call: a row costs about as much as 40 candidates (parsing its rule,
# building the expansion), so 500,000 is about 12,500 rows or 500,000 candidates,
# each well under a second (task 3c measures it).
MAX_WORK = 500_000
ROW_WORK = 40

type Taken = set[tuple[uuid.UUID, datetime]]


def _max_work() -> int:
    return MAX_WORK


@dataclass(slots=True)
class Budget:
    """What one call may expand, and what it spent so far."""

    occurrences: int = MAX_OCCURRENCES
    work: int = field(default_factory=_max_work)
    counter: Counter = field(default_factory=Counter)
    rows: int = 0

    def spent(self) -> int:
        return self.rows * ROW_WORK + self.counter.candidates

    def rows_allowed(self) -> int:
        """The most rows a caller should load: one more is over the budget."""
        return self.work // ROW_WORK

    def charge(self, rows: int = 0) -> None:
        self.rows += rows
        if self.spent() > self.work:
            raise TooDense


def effective(
    rows: Sequence[CalendarEvent],
    taken: Taken,
    start: datetime,
    end: datetime,
    *,
    viewer_zone: str,
    budget: Budget,
) -> list[tuple[Occurrence, CalendarEvent]]:
    """See the module's contract."""
    budget.charge(len(rows))
    found: list[tuple[Occurrence, CalendarEvent]] = []
    for event in rows:
        room = budget.occurrences - len(found)
        for occurrence in _expand(event, start, end, viewer_zone, room, budget.counter):
            if not (event.recurring and (event.id, occurrence.recurrence_id) in taken):
                found.append((occurrence, event))
        budget.charge()
    if len(found) > budget.occurrences:
        raise TooDense
    return found


def _expand(
    event: CalendarEvent, start: datetime, end: datetime, zone: str, room: int, counter: Counter
) -> list[Occurrence]:
    """The event's occurrences in the window; all-day ones by the viewer's days."""
    try:
        series = series_of(event)
        if not event.all_day:
            return recurrence.occurrences(series, start, end, limit=room, counter=counter)
        near = recurrence.occurrences(
            series, start - ALL_DAY_REACH, end + ALL_DAY_REACH, limit=room, counter=counter
        )
    except (recurrence.SeriesInvalid, ValueError):
        logger.warning("calendar.series_unreadable", extra={"event_id": str(event.id)})
        return []
    return [
        o for o in near if floating_day(o.start, zone) < end and floating_day(o.end, zone) > start
    ]
