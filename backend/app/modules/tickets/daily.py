"""The team board for the daily (plan M4b decisions 5 and 6): the board of a space
grouped by assignee. A row per person with tickets under the filters (by name, at most
MAX_ROWS of them, `truncated` beyond), then one for the tickets assigned to nobody; per
status of the space a cell with its count, how many of them changed status since the
last working day began, and its first `limit` tickets in board order, each flagged
`changed`; a cell's `next_cursor` continues in the column of its status
(`/board/{status_id}?assignee=<id>|none`). Seen by whoever may read the space's
tickets (404 `space.not_found` otherwise); a fixed number of statements per call.

"Since the last working day" (`last_working_day_start`): from 0:00 of the latest
weekday (Monday to Friday) before today, so on a Monday since Friday; there is no
holiday calendar, and days are UTC days (organisations have no time zone setting). A
ticket's status change time is `work_item.status_changed_at` (set by the database in
the transaction that writes the change, as is the change's timeline entry).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.modules.tickets.base import ticket_repository, with_tags
from app.modules.tickets.daily_repository import DailyRepository, Group
from app.modules.tickets.listing import Filters
from app.modules.tickets.repository import TicketView
from app.modules.tickets.statuses import status_repository
from app.modules.tickets.view_repository import board_position
from app.modules.tickets.views import Column, encode

MAX_ROWS = 100
WORKING_DAYS = range(5)  # Monday (0) to Friday (4)


def last_working_day_start(now: datetime) -> datetime:
    """0:00 (UTC) of the latest working day before `now`'s day."""
    day = now.astimezone(UTC).date() - timedelta(days=1)
    while day.weekday() not in WORKING_DAYS:
        day -= timedelta(days=1)
    return datetime.combine(day, time(0), tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Cell:
    status_id: uuid.UUID
    count: int
    changed: int
    items: list[TicketView]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class Row:
    assignee_id: uuid.UUID | None  # None: assigned to nobody
    assignee_name: str | None
    cells: list[Cell]


@dataclass(frozen=True, slots=True)
class Daily:
    columns: list[Column]  # the statuses with their counts (the tickets are in the rows)
    rows: list[Row]
    changed_since: datetime
    truncated: bool


def _people(groups: list[Group]) -> list[tuple[uuid.UUID, str | None]]:
    named = {g.assignee_id: g.assignee_name for g in groups if g.assignee_id is not None}
    return sorted(named.items(), key=lambda p: ((p[1] or "").casefold(), str(p[0])))


class DailyBoard:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def board(self, actor: Actor, space_id: uuid.UUID, filters: Filters, limit: int) -> Daily:
        await require(self.session, actor, Action.TICKET_READ, space_id)
        since = last_working_day_start(datetime.now(UTC))
        statuses = await status_repository(self.session, actor).in_space(space_id)
        repo = DailyRepository(self.session, ticket_repository(self.session, actor).scope)
        groups = await repo.groups(space_id, filters, since)
        people = _people(groups)
        shown = people[:MAX_ROWS]
        unassigned = any(g.assignee_id is None for g in groups)
        ids = [person_id for person_id, _ in shown]
        cells = await repo.cells(space_id, filters, ids, unassigned, limit + 1)
        views = [v for rows in cells.values() for v in rows[:limit]]
        tagged = {v.ticket.id: v for v in await with_tags(self.session, actor, views)}
        by_group = {(g.assignee_id, g.status_id): g for g in groups}
        rows = []
        for person_id, name in [*shown, *([(None, None)] if unassigned else [])]:
            row_cells = []
            for status in statuses:
                group = by_group.get((person_id, status.id))
                found = cells.get((person_id, status.id), [])
                items = [tagged[v.ticket.id] for v in found[:limit]]
                more = len(found) > limit
                cursor = encode(board_position(items[-1])) if more else None
                count, changed = (group.count, group.changed) if group else (0, 0)
                row_cells.append(Cell(status.id, count, changed, items, cursor))
            rows.append(Row(person_id, name, row_cells))
        totals = {s.id: sum(g.count for g in groups if g.status_id == s.id) for s in statuses}
        columns = [Column(s, totals[s.id], [], None) for s in statuses]
        return Daily(columns, rows, since, len(people) > MAX_ROWS)
