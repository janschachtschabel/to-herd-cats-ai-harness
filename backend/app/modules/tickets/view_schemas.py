from pydantic import BaseModel

from app.modules.tickets.models import StatusCategory
from app.modules.tickets.schemas import ChildCounts, StatusRef, TicketSummaryOut
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


class BoardOut(BaseModel):
    """The space's statuses in their order, each a column."""

    columns: list[BoardColumnOut]


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
