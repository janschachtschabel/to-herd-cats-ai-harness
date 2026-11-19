"""SQL for events. Every statement is scoped by the organisation and leaves out
tombstones and the events of archived calendars; who may see what comes in as SQL
(`sight.py`), so lists filter in the statement."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, Select, and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.models import Calendar

UID_INDEX = "uq_calendar_event_uid"
# All-day events float on UTC days: a viewer's day lies up to 14 hours to either side.
ALL_DAY_REACH = timedelta(hours=14)


class UidTaken(Exception):
    """Another live event of the calendar has the UID (and recurrence id)."""


def _live() -> ColumnElement[bool]:
    return and_(CalendarEvent.deleted_at.is_(None), Calendar.archived_at.is_(None))


class EventRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    def _select(self) -> Select[CalendarEvent]:
        return (
            select(CalendarEvent)
            .join(Calendar, Calendar.id == CalendarEvent.calendar_id)
            .where(CalendarEvent.org_id == self.org_id, _live())
        )

    async def find(self, event_id: uuid.UUID, seen: ColumnElement[bool]) -> CalendarEvent | None:
        """The event if it passes `seen`, in one statement: one the caller may not see
        costs what an unknown id costs."""
        found: CalendarEvent | None = await self.session.scalar(
            self._select().where(CalendarEvent.id == event_id, seen)
        )
        return found

    async def add(self, event: CalendarEvent) -> CalendarEvent:
        """Stores the event; `UidTaken` when the calendar has a live event with its UID
        (and recurrence id). The rest of the transaction stays (a savepoint)."""
        try:
            async with self.session.begin_nested():
                self.session.add(event)
                await self.session.flush()
        except IntegrityError as exc:
            if UID_INDEX in str(exc.orig):
                raise UidTaken from None
            raise
        return event

    async def in_window(
        self,
        rule: ColumnElement[bool],
        reads: ColumnElement[bool],
        start: datetime,
        end: datetime,
        *,
        calendar_ids: list[uuid.UUID] | None,
        title: str | None,
        full: ColumnElement[bool],
        limit: int,
    ) -> list[tuple[CalendarEvent, bool]]:
        """The events passing `rule` that can reach `[start, end)` (all-day ones
        within `ALL_DAY_REACH` of it), each with whether the caller reads its space;
        at most `limit`. With `title`, only those whose title holds it among those the
        caller sees in full (`full`): a search never answers by hidden content."""
        stmt = (
            select(CalendarEvent, reads)
            .join(Calendar, Calendar.id == CalendarEvent.calendar_id)
            .where(
                CalendarEvent.org_id == self.org_id,
                _live(),
                rule,
                or_(
                    and_(
                        CalendarEvent.all_day.is_(False),
                        CalendarEvent.starts_at < end,
                        or_(
                            CalendarEvent.recurs_until.is_(None),
                            CalendarEvent.recurs_until >= start,
                        ),
                    ),
                    and_(
                        CalendarEvent.all_day.is_(True),
                        CalendarEvent.starts_at < end + ALL_DAY_REACH,
                        or_(
                            CalendarEvent.recurs_until.is_(None),
                            CalendarEvent.recurs_until >= start - ALL_DAY_REACH,
                        ),
                    ),
                ),
            )
            .order_by(CalendarEvent.starts_at, CalendarEvent.id)
            .limit(limit)
        )
        if calendar_ids is not None:
            stmt = stmt.where(CalendarEvent.calendar_id.in_(calendar_ids))
        if title is not None:
            stmt = stmt.where(full, CalendarEvent.title.icontains(title, autoescape=True))
        return [(row[0], bool(row[1])) for row in await self.session.execute(stmt)]

    async def overridden(self, series_ids: list[uuid.UUID]) -> set[tuple[uuid.UUID, datetime]]:
        """(series, recurrence id) of every live override of the series, wherever it
        moved to: the occurrence it takes the place of is not listed."""
        if not series_ids:
            return set()
        stmt = select(CalendarEvent.series_id, CalendarEvent.recurrence_id).where(
            CalendarEvent.org_id == self.org_id,
            CalendarEvent.deleted_at.is_(None),
            CalendarEvent.series_id.in_(series_ids),
        )
        return {
            (row[0], row[1])
            for row in await self.session.execute(stmt)
            if row[0] is not None and row[1] is not None
        }
