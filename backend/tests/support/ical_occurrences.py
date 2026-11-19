"""What an iCalendar draft shows in a window: its series' occurrences, each replaced by
its override where one names it, as `(start, end)` pairs in UTC."""

from datetime import UTC, datetime
from pathlib import Path

from app.modules.calendars import recurrence
from app.modules.calendars.ical.drafts import EventDraft

DATA = Path(__file__).parent.parent / "data" / "ical"
WIDE_FROM = datetime(2020, 1, 1, tzinfo=UTC)
WIDE_TO = datetime(2030, 1, 1, tzinfo=UTC)

Span = tuple[datetime, datetime]


def sample(name: str) -> bytes:
    return (DATA / name).read_bytes()


def effective(
    draft: EventDraft, start: datetime = WIDE_FROM, end: datetime = WIDE_TO
) -> list[Span]:
    replaced = {override.recurrence_id for override in draft.overrides}
    spans = [
        (found.start, found.end)
        for found in recurrence.occurrences(draft.series, start, end)
        if found.recurrence_id not in replaced
    ]
    for override in draft.overrides:
        spans += [
            (found.start, found.end)
            for found in recurrence.occurrences(override.series, start, end)
        ]
    return sorted(spans)


def utc(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=UTC)
