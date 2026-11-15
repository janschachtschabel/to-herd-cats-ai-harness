"""The ticket list's filters, sort orders and cursors (plan M4 task 2).

Sort orders, each with the ticket number as the tie-breaker (unique per organisation):
- `updated`: last changed first;
- `due`: earliest due first, tickets without a date last;
- `priority`: most urgent first;
- `number`: newest first.

A cursor is the sort order, the last row's sort value and its number; a cursor of
another sort order, or anything else that does not decode, is 422 (never a 500).
"""

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum

from app.core.errors import ValidationFailed
from app.modules.tickets.models import Priority, StatusCategory, TicketKind


class Sort(StrEnum):
    UPDATED = "updated"
    DUE = "due"
    PRIORITY = "priority"
    NUMBER = "number"


LAST_DAY = date(9999, 12, 31)  # where tickets without a due date sort

SortValue = datetime | date | int


@dataclass(frozen=True, slots=True)
class Filters:
    """Each set filter narrows the list; None filters nothing."""

    space_id: uuid.UUID | None = None
    status_categories: tuple[StatusCategory, ...] = ()
    status_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    agent_assignee_id: uuid.UUID | None = None  # tickets assigned to this agent
    unassigned: bool = False  # only tickets assigned to nobody
    reporter_id: uuid.UUID | None = None
    kind: TicketKind | None = None
    priority: Priority | None = None
    parent_id: uuid.UUID | None = None
    q: str | None = None
    due_before: date | None = None
    tag_ids: tuple[uuid.UUID, ...] = ()  # tickets carrying every one of them
    epic_id: uuid.UUID | None = None  # an epic's children and their children
    sprint_id: uuid.UUID | None = None
    backlog: bool = False  # only tickets in no sprint


@dataclass(frozen=True, slots=True)
class Position:
    """Where the page before ended: its last row's sort value and number."""

    value: SortValue
    number: int


def sort_value(sort: Sort, updated_at: datetime, due_on: date | None, priority: str) -> SortValue:
    if sort == Sort.UPDATED:
        return updated_at
    if sort == Sort.DUE:
        return due_on or LAST_DAY
    if sort == Sort.PRIORITY:
        return Priority(priority).rank
    return 0  # `number`: the number alone orders


def encode(sort: Sort, position: Position) -> str:
    value = position.value
    shown: str | int = value.isoformat() if isinstance(value, date) else value
    raw = json.dumps([sort.value, shown, position.number]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode(sort: Sort, cursor: str) -> Position:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        kind, shown, number = json.loads(raw.decode())
        if kind != sort.value or type(number) is not int or not 0 <= number < 2**31:
            raise ValueError("not a cursor of this order")
        return Position(_value(sort, shown), number)
    except Exception as exc:
        error = ValidationFailed("Invalid cursor", code="validation_failed")
        raise error from exc


def _value(sort: Sort, shown: object) -> SortValue:
    if sort == Sort.UPDATED and isinstance(shown, str):
        moment = datetime.fromisoformat(shown)
        if moment.tzinfo is None:
            raise ValueError("naive timestamp")
        return moment.astimezone(UTC)
    if sort == Sort.DUE and isinstance(shown, str):
        return date.fromisoformat(shown)
    if sort in (Sort.PRIORITY, Sort.NUMBER) and type(shown) is int:
        if not 0 <= shown < 2**31:
            raise ValueError("out of range")
        return shown
    raise TypeError("bad cursor value")
