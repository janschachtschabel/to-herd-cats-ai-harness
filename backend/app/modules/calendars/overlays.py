"""Overlays (plan M10 decision 16, task 9): what the calendar shows beside events
without storing anything: ticket due dates, sprints and the next terms of
automations, each read from its own module's repository, read only.

- Which: tickets and sprints of the spaces one belongs to (`access.member_space_ids`,
  the calendar lists' rule, decision 3 C1: an admin's overlays hold only her own
  spaces, never what admin power opens, so nothing here is audited; `ticket.read` is a
  reading right every member holds). Tickets not done or cancelled (a status's
  category) with a due day in the range; sprints of any state that hold a day of it.
  Automations: those `automations/sight.py` shows the person, active, whose next
  term lies in the range, and only where their place is in one of her spaces or the
  automation is her own (so a DM's automation shows its owner alone, and admins'
  `agent.manage` adds no foreign space either). One statement per kind, filtered in
  SQL.
- The range `[start, end)` is in days (the end excluded, like the window's `to`),
  within 1900-01-01 and 2400-01-01. A ticket lies on its due day, a sprint from its
  first to its last day; an automation's term on its day in `viewer_zone` (default
  UTC), the instant beside it (`at`).
- Paged by (starts_on, kind, id); automations, of which a day may hold several
  terms, by (starts_on, kind, at, id), which is the same order refined (the day of a
  term rises with its instant). A cursor holds the viewer zone and is valid with it
  only (422 `calendar.cursor_time_zone`).
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Actor, member_space_ids
from app.core.errors import ValidationFailed
from app.core.pagination import PageParams
from app.core.repository import DayKey
from app.modules.automations.manage_repository import ManageRepository
from app.modules.automations.sight import sight_of
from app.modules.calendars import zones
from app.modules.tickets.models import ticket_key
from app.modules.tickets.repository import TicketScope
from app.modules.tickets.sprint_repository import SprintRepository
from app.modules.tickets.view_repository import ViewRepository

FIRST_DAY = date(1900, 1, 1)
LAST_DAY = date(2400, 1, 1)  # as the end of a range: all of 2399
VIEWER_ZONE = "UTC"
_NO_TERM = datetime.min.replace(tzinfo=UTC)  # the sort key of what has no instant


class OverlayKind(StrEnum):  # in the order of a page within a day
    AUTOMATIONS = "automations"
    SPRINTS = "sprints"
    TICKETS = "tickets"


@dataclass(frozen=True, slots=True)
class Overlay:
    kind: OverlayKind
    id: uuid.UUID
    space_id: uuid.UUID | None  # an automation in a DM has none
    starts_on: date
    ends_on: date  # the last day, included
    ref: str  # a ticket's key, else the id
    title: str  # a ticket's title, a sprint's name, an automation's agent
    at: datetime | None = None  # an automation's term

    @property
    def key(self) -> tuple[date, str, datetime, uuid.UUID]:
        return (self.starts_on, self.kind, self.at or _NO_TERM, self.id)


@dataclass(frozen=True, slots=True)
class _After:
    """The cursor: the last overlay of the page before."""

    day: date
    kind: OverlayKind
    id: uuid.UUID
    at: datetime | None


async def list_overlays(
    session: AsyncSession,
    actor: Actor,
    *,
    start: date,
    end: date,
    kinds: Collection[OverlayKind],
    params: PageParams,
    viewer_zone: str | None = None,
) -> pagination.Page[Overlay]:
    """See the module's docstring."""
    if not (FIRST_DAY <= start <= LAST_DAY and FIRST_DAY <= end <= LAST_DAY):
        raise ValidationFailed(code="calendar.window_out_of_range")
    if end <= start:
        raise ValidationFailed(code="calendar.invalid_window")
    zone = viewer_zone or VIEWER_ZONE
    try:
        zones.zone(zone)
    except zones.ZoneUnknown:
        raise ValidationFailed(code="calendar.invalid_time_zone") from None
    after = _after(params.cursor, zone)
    limit = params.limit + 1  # one more of each kind tells whether there is more
    scope = TicketScope(actor.org_id, member_space_ids(actor))
    found: list[Overlay] = []
    if OverlayKind.TICKETS in kinds:
        due = ViewRepository(session, scope)
        tickets = await due.due_between(start, end, _key(OverlayKind.TICKETS, after), limit)
        found += [
            Overlay(OverlayKind.TICKETS, t.id, t.space_id, d, d, ticket_key(t.number), t.title)
            for t in tickets
            if (d := t.due_on) is not None
        ]
    if OverlayKind.SPRINTS in kinds:
        held = SprintRepository(session, scope)
        sprints = await held.overlapping(start, end, _key(OverlayKind.SPRINTS, after), limit)
        found += [
            Overlay(
                OverlayKind.SPRINTS, s.id, s.space_id, s.starts_on, s.ends_on, str(s.id), s.name
            )
            for s in sprints
        ]
    if OverlayKind.AUTOMATIONS in kinds:
        found += await _terms(session, actor, start, end, zone, after, limit)
    found.sort(key=lambda overlay: overlay.key)
    page = found[: params.limit]
    more = len(found) > params.limit
    return pagination.Page[Overlay](
        items=page, next_cursor=_cursor(page[-1], zone) if more else None
    )


async def _terms(
    session: AsyncSession,
    actor: Actor,
    start: date,
    end: date,
    zone: str,
    after: _After | None,
    limit: int,
) -> list[Overlay]:
    sight = await sight_of(session, actor)
    if not sight.sees:  # no `ai.use`: no automation at all
        return []
    lower, upper = _midnight(start, zone), _midnight(end, zone)
    past: tuple[datetime, uuid.UUID] | None = None
    if after is not None:
        if OverlayKind.AUTOMATIONS == after.kind:
            if after.at is None:
                raise pagination.invalid_cursor()
            past = (after.at, after.id)
        else:  # a later kind: the cursor's day is done for automations
            lower = max(lower, _midnight(after.day + timedelta(days=1), zone))
    terms = await ManageRepository(session, actor.org_id).terms_between(
        sight,
        spaces=member_space_ids(actor),
        owner_id=actor.principal.id,
        start=lower,
        end=upper,
        after=past,
        limit=limit,
    )
    found = []
    for term in terms:
        at = term.automation.next_due_at
        assert at is not None  # an active automation in the range has a term
        day = zones.wall(at, zone).date()
        automation_id = term.automation.id
        found.append(
            Overlay(
                OverlayKind.AUTOMATIONS,
                automation_id,
                term.space_id,
                day,
                day,
                str(automation_id),
                term.agent_name,
                at,
            )
        )
    return found


def _key(kind: OverlayKind, after: _After | None) -> DayKey | None:
    """Where a kind ordered by (day, id) goes on after the cursor: past its day if
    the cursor's kind comes later, past its id on its day if it is this kind, and
    from its day if the cursor's kind comes earlier."""
    if after is None:
        return None
    if kind < after.kind:
        return DayKey(after.day + timedelta(days=1))
    if kind == after.kind:
        return DayKey(after.day, after.id)
    return DayKey(after.day)


def _midnight(day: date, zone: str) -> datetime:
    """The first instant of `day` in `zone` (a day that begins in a gap begins when
    the gap ends)."""
    return zones.localise(datetime.combine(day, time()), zone)


def _cursor(last: Overlay, zone: str) -> str:
    at = last.at.isoformat() if last.at is not None else ""
    return pagination.encode_parts_cursor(
        last.starts_on.isoformat(), last.kind, str(last.id), zone, at
    )


def _after(cursor: str | None, zone: str) -> _After | None:
    if not cursor:
        return None
    day, kind, id_, made_in, at = pagination.decode_parts_cursor(cursor, 5)
    try:
        term = datetime.fromisoformat(at) if at else None
        if term is not None and term.tzinfo is None:
            raise ValueError("a term is an instant")
        after = _After(
            date.fromisoformat(day),
            OverlayKind(kind),
            uuid.UUID(id_),
            term.astimezone(UTC) if term is not None else None,
        )
    except Exception as exc:  # untrusted input: any failure is 422 (`core/pagination.py`)
        raise pagination.invalid_cursor(exc) from exc
    if made_in != zone:
        raise ValidationFailed(code="calendar.cursor_time_zone")
    if not FIRST_DAY <= after.day <= LAST_DAY:
        raise pagination.invalid_cursor()
    return after
