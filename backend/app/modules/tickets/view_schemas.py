import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.tickets.daily import Cell, Daily, Row
from app.modules.tickets.models import StatusCategory
from app.modules.tickets.repository import TicketView
from app.modules.tickets.schemas import ChildCounts, PersonOut, StatusRef, TicketSummaryOut
from app.modules.tickets.views import Column, Epic


def child_counts(children: dict[StatusCategory, int]) -> ChildCounts:
    return ChildCounts(**{c.value: children.get(c, 0) for c in StatusCategory})


class BoardColumnOut(BaseModel):
    """A status of the board: how many tickets it holds under the filters, the first
    of them in board order (priority, due date with none last, number), and the
    cursor for more (`GET /api/spaces/{space_id}/board/{status_id}`)."""

    status: StatusRef
    count: int
    items: list[TicketSummaryOut]
    next_cursor: str | None

    @classmethod
    def of(cls, column: Column) -> "BoardColumnOut":
        s = column.status
        return cls(
            status=StatusRef(id=s.id, name=s.name, category=s.category),
            count=column.count,
            items=[TicketSummaryOut.of(v) for v in column.items],
            next_cursor=column.next_cursor,
        )


class DailyCardOut(TicketSummaryOut):
    """A ticket of the daily view; `changed`: its status changed (or it was made) since
    the board's `changed_since`."""

    changed: bool

    @classmethod
    def of_daily(cls, view: TicketView, since: datetime) -> "DailyCardOut":
        changed = view.ticket.status_changed_at >= since
        return cls.model_validate({**cls.fields_of(view), "changed": changed})


class BoardCellOut(BaseModel):
    """A person's tickets in one status: how many, how many changed status since the
    board's `changed_since`, the first of them in board order, and the cursor for more
    (`GET /api/spaces/{space_id}/board/{status_id}?assignee=<id>|none`)."""

    status_id: uuid.UUID
    count: int
    changed: int
    items: list[DailyCardOut]
    next_cursor: str | None

    @classmethod
    def of(cls, cell: Cell, since: datetime) -> "BoardCellOut":
        return cls(
            status_id=cell.status_id,
            count=cell.count,
            changed=cell.changed,
            items=[DailyCardOut.of_daily(v, since) for v in cell.items],
            next_cursor=cell.next_cursor,
        )


class BoardRowOut(BaseModel):
    """A person's row (`assignee` null: the tickets assigned to nobody), a cell per
    status of the space in order."""

    assignee: PersonOut | None
    cells: list[BoardCellOut]

    @classmethod
    def of(cls, row: Row, since: datetime) -> "BoardRowOut":
        assignee = None
        if row.assignee_id is not None:
            assignee = PersonOut(type=row.assignee_type, id=row.assignee_id, name=row.assignee_name)
        return cls(assignee=assignee, cells=[BoardCellOut.of(c, since) for c in row.cells])


class BoardOut(BaseModel):
    """The space's statuses in their order, each a column. Grouped by assignee
    (`group_by=assignee`, the daily view): `columns` carry the statuses and their
    counts only (no tickets), `rows` the people (by name, at most 100,
    `rows_truncated` beyond; the row of the unassigned last) and `changed_since` the
    moment the last working day began (0:00 UTC; on a Monday: Friday's)."""

    columns: list[BoardColumnOut]
    rows: list[BoardRowOut] | None = None
    changed_since: datetime | None = None
    rows_truncated: bool = False

    @classmethod
    def of_daily(cls, daily: Daily) -> "BoardOut":
        return cls(
            columns=[BoardColumnOut.of(c) for c in daily.columns],
            rows=[BoardRowOut.of(r, daily.changed_since) for r in daily.rows],
            changed_since=daily.changed_since,
            rows_truncated=daily.truncated,
        )


class EpicOut(TicketSummaryOut):
    """An epic with how many children it has per status category (its progress)."""

    children: ChildCounts

    @classmethod
    def from_epic(cls, epic: Epic) -> "EpicOut":
        return cls.model_validate(
            {**cls.fields_of(epic.view), "children": child_counts(epic.children)}
        )


class TicketCountsOut(BaseModel):
    """For the sidebar: the caller's tickets that are open, active or in review."""

    assigned_open: int
