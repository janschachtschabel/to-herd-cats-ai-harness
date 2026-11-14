"""Sprints of a space (plan M4b, decisions 1 to 3).

Rights only from `core/access.py`: reading needs `ticket.read` in the space, making,
changing, starting and closing a sprint `ticket.assign` (from moderator); a sprint of a
space the actor cannot read is 404 `sprint.not_found`, like an unknown id.

Rules:
- states in order: planned → active → closed; at most one active sprint per space
  (409 `sprint.active_exists`; the unique index `uq_sprint_space_id_active` holds it
  under concurrent starts); only planned or active sprints change (409
  `sprint.state_invalid`); a sprint ends no earlier than it starts and lies between
  2000-01-01 and 2100-12-31 (422 `sprint.dates_invalid`);
- closing (an active sprint) moves its unfinished tickets (category neither `done` nor
  `cancelled`) to the space's next planned sprint (`next`: the one that starts first;
  422 `sprint.next_missing` without one) or back to the backlog (`backlog`), and
  records the tally: tickets in the sprint, done, carried. Each moved ticket gets a new
  version and one `ticket.updated` event (field `sprint`), all in the closing's
  transaction.
Every change names the version it read (409 `sprint.version_conflict`), is one
`sprint.*` event and, where it creates, starts or closes, audited.
"""

import builtins
import uuid
from collections.abc import Collection
from datetime import date
from enum import StrEnum
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, decode_score_cursor, encode_score_cursor
from app.modules.audit.recorder import record
from app.modules.tickets.base import ticket_repository
from app.modules.tickets.events import (
    SPRINT_CLOSED,
    SPRINT_CREATED,
    SPRINT_STARTED,
    SPRINT_UPDATED,
    TICKET_UPDATED,
    Field,
    sprint_event,
    ticket_event,
)
from app.modules.tickets.models import (
    FIRST_SPRINT_DAY,
    LAST_SPRINT_DAY,
    Sprint,
    SprintState,
    StatusCategory,
)
from app.modules.tickets.sprint_repository import FINISHED, SprintRepository, order_key
from app.modules.tickets.statuses import status_repository
from app.modules.tickets.thread_repository import TicketThreadRepository

EDITABLE = ("name", "goal", "starts_on", "ends_on")


class MoveOpenTo(StrEnum):
    NEXT = "next"
    BACKLOG = "backlog"


def sprint_not_found() -> NotFound:
    return NotFound(code="sprint.not_found")


def sprint_repository(session: AsyncSession, actor: Actor) -> SprintRepository:
    """The actor's view of the sprints: the spaces where it may read tickets."""
    return SprintRepository(session, ticket_repository(session, actor).scope)


def _check_dates(starts_on: date, ends_on: date) -> None:
    if ends_on < starts_on:
        raise ValidationFailed(
            "A sprint ends no earlier than it starts", code="sprint.dates_invalid"
        )
    if starts_on < FIRST_SPRINT_DAY or ends_on > LAST_SPRINT_DAY:
        raise ValidationFailed(
            "A sprint lies between 2000-01-01 and 2100-12-31", code="sprint.dates_invalid"
        )


def _state_invalid() -> Conflict:
    return Conflict("Not possible in the sprint's state", code="sprint.state_invalid")


class SprintService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        actor: Actor,
        space_id: uuid.UUID,
        states: Collection[SprintState],
        params: PageParams,
    ) -> pagination.Page[Sprint]:
        await require(self.session, actor, Action.TICKET_READ, space_id)
        after = None
        if params.cursor:
            key, id_ = decode_score_cursor(params.cursor)
            if key != int(key) or not 0 <= key < 3 * 100_000_000:
                raise ValidationFailed("Invalid cursor", code="validation_failed")
            after = (int(key), id_)
        rows = await sprint_repository(self.session, actor).page(
            space_id, states, after, params.limit + 1
        )
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = None
        if more:
            last = items[-1]
            cursor = encode_score_cursor(
                order_key(last.state, last.starts_on, last.ends_on), last.id
            )
        return pagination.Page[Sprint](items=items, next_cursor=cursor)

    async def create(
        self,
        actor: Actor,
        space_id: uuid.UUID,
        *,
        name: str,
        goal: str,
        starts_on: date,
        ends_on: date,
    ) -> Sprint:
        await require(self.session, actor, Action.TICKET_ASSIGN, space_id)
        _check_dates(starts_on, ends_on)
        sprint = await sprint_repository(self.session, actor).add(
            Sprint(
                org_id=actor.org_id,
                space_id=space_id,
                name=name,
                goal=goal,
                starts_on=starts_on,
                ends_on=ends_on,
                state=SprintState.PLANNED,
            )
        )
        await self._event(actor, SPRINT_CREATED, sprint, [])
        await self._audit(actor, "sprint.created", sprint, {})
        return sprint

    async def update(
        self, actor: Actor, sprint_id: uuid.UUID, version: int, values: dict[str, Any]
    ) -> Sprint:
        """`values`: the fields the client sent (none of them null)."""
        _, sprint = await self._managed(actor, sprint_id, version)
        if sprint.state == SprintState.CLOSED:
            raise _state_invalid()
        changed = [n for n in EDITABLE if n in values and values[n] != getattr(sprint, n)]
        if not changed:
            return sprint
        _check_dates(
            values.get("starts_on", sprint.starts_on), values.get("ends_on", sprint.ends_on)
        )
        for name in changed:
            setattr(sprint, name, values[name])
        sprint.version += 1
        await self.session.flush()
        await self._event(actor, SPRINT_UPDATED, sprint, changed)
        return sprint

    async def start(self, actor: Actor, sprint_id: uuid.UUID, version: int) -> Sprint:
        repo, sprint = await self._managed(actor, sprint_id, version)
        if sprint.state != SprintState.PLANNED:
            raise _state_invalid()
        if await repo.active_exists(sprint.space_id):
            raise _active_exists()
        sprint.state = SprintState.ACTIVE
        sprint.version += 1
        try:  # a start racing this one: the unique index decides (review focus 2)
            async with self.session.begin_nested():
                await self.session.flush()
        except IntegrityError:
            raise _active_exists() from None
        await self._event(actor, SPRINT_STARTED, sprint, ["state"])
        await self._audit(actor, "sprint.started", sprint, {})
        return sprint

    async def close(
        self, actor: Actor, sprint_id: uuid.UUID, version: int, move_open_to: MoveOpenTo
    ) -> Sprint:
        repo, sprint = await self._managed(actor, sprint_id, version)
        if sprint.state != SprintState.ACTIVE:
            raise _state_invalid()
        target = None
        if move_open_to == MoveOpenTo.NEXT:
            target = await repo.next_planned(sprint.space_id)
            if target is None:
                raise ValidationFailed(
                    "No planned sprint to carry on in", code="sprint.next_missing"
                )
        # Lock order sprint → the space's statuses → tickets: a status deletion holds the
        # status lock while it moves its tickets, so the two never lock tickets at once
        # (in crossing orders, module review M4b finding 2).
        await status_repository(self.session, actor).lock_space(sprint.space_id)
        tickets = await repo.lock_tickets(sprint.id)
        categories = await repo.categories({status_id for _, status_id in tickets})
        open_ = [t for t, s in tickets if categories.get(s) not in FINISHED]
        done = sum(1 for _, s in tickets if categories.get(s) == StatusCategory.DONE)
        await repo.move_tickets(open_, target.id if target else None)
        sprint.state = SprintState.CLOSED
        sprint.planned_count, sprint.done_count, sprint.carried_count = (
            len(tickets),
            done,
            len(open_),
        )
        sprint.version += 1
        await self.session.flush()
        threads = await TicketThreadRepository(self.session, actor.org_id).thread_ids(open_)
        for ticket_id in open_:  # each moved ticket changed: one event each
            await ticket_event(
                self.session,
                actor,
                TICKET_UPDATED,
                ticket_id=ticket_id,
                space_id=sprint.space_id,
                conversation_id=threads.get(ticket_id),
                changes={Field.SPRINT: (sprint.id, target.id if target else None)},
            )
        await self._event(actor, SPRINT_CLOSED, sprint, ["state"])
        tally = {"planned": len(tickets), "done": done, "carried": len(open_)}
        await self._audit(
            actor, "sprint.closed", sprint, {"move_open_to": move_open_to.value, **tally}
        )
        return sprint

    async def _managed(
        self, actor: Actor, sprint_id: uuid.UUID, version: int
    ) -> tuple[SprintRepository, Sprint]:
        """The sprint, held for a change by someone with `ticket.assign` in its space,
        at the version the client read."""
        repo = sprint_repository(self.session, actor)
        sprint = await repo.get(sprint_id)
        if sprint is None:
            raise sprint_not_found()
        try:
            await require(self.session, actor, Action.TICKET_ASSIGN, sprint.space_id)
        except NotFound:
            raise sprint_not_found() from None
        sprint = await repo.get(sprint_id, lock=True)
        if sprint is None:  # the space went away meanwhile
            raise sprint_not_found()
        if sprint.version != version:
            raise Conflict(
                code="sprint.version_conflict", details={"current_version": sprint.version}
            )
        return repo, sprint

    async def _event(
        self, actor: Actor, type_: str, sprint: Sprint, fields: builtins.list[str]
    ) -> None:
        await sprint_event(
            self.session, actor, type_, sprint_id=sprint.id, space_id=sprint.space_id, fields=fields
        )

    async def _audit(
        self, actor: Actor, action: str, sprint: Sprint, details: dict[str, Any]
    ) -> None:
        details = {"space_id": str(sprint.space_id), **details}
        await record(self.session, actor, action, "sprint", sprint.id, details)


def _active_exists() -> Conflict:
    return Conflict("The space has an active sprint", code="sprint.active_exists")


async def hold_for_move(
    session: AsyncSession, actor: Actor, number: int, sprint_id: uuid.UUID | None
) -> dict[uuid.UUID, Sprint]:
    """Before ticket `number` changes its sprint: the sprints it leaves and joins (of its
    space), held in the order of their ids, ahead of the ticket's own lock (review focus
    2: sprints before tickets, as a closing takes them)."""
    found = await ticket_repository(session, actor).by_number(number)
    if found is None:
        return {}
    ids = {i for i in (found.sprint_id, sprint_id) if i is not None}
    return await sprint_repository(session, actor).hold(found.space_id, ids)


def check_sprint(held: dict[uuid.UUID, Sprint], space_id: uuid.UUID, sprint_id: uuid.UUID) -> None:
    """A ticket joins only a planned or active sprint of its own space; anything else is
    422 `ticket.sprint_invalid`, the same for a sprint of another space as for none."""
    sprint = held.get(sprint_id)
    if sprint is None or sprint.space_id != space_id or sprint.state == SprintState.CLOSED:
        raise ValidationFailed(
            "Not an open sprint of the ticket's space", code="ticket.sprint_invalid"
        )
