"""The SQL of tickets. `TicketRepository` is scoped by the actor's organisation and the
spaces where it may read tickets (`TicketScope`): a ticket of any other space is never
even loaded, whether asked for by number, by id, as a parent or in a list. Looking up
a number that is taken but hidden and one that is free is the same statement with the
same empty answer (review focus 1).

Locks (review focus 4): a written ticket `FOR UPDATE`, a parent being set `FOR SHARE`
(see `hierarchy.py`; the two in the order of their ids, `base.editable`), a status
being taken `FOR KEY SHARE` (`status_repository.py`).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    case,
    cast,
    exists,
    func,
    literal,
    or_,
    select,
    tuple_,
)
from sqlalchemy.dialects.postgresql import REGCONFIG, insert
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, defer

from app.core.access_repository import person_holds_role
from app.core.permissions import SPACE_ACTION_MIN_ROLE, Action
from app.core.principal import PrincipalType
from app.modules.tags.models import SubjectType, Tag, Tagging
from app.modules.tickets.listing import LAST_DAY, Filters, Position, Sort
from app.modules.tickets.models import (
    Priority,
    StatusCategory,
    TicketCounter,
    TicketKind,
    TicketStatus,
    WorkItem,
)
from app.modules.users.models import User

_GERMAN = cast(literal("german"), REGCONFIG)
_SIMPLE = cast(literal("simple"), REGCONFIG)
# A ticket with its status, its parent's id, number, title and kind, and the names of
# its assignee and its reporter.
ViewSelect = Select[WorkItem, TicketStatus, uuid.UUID, int, str, TicketKind, str, str]
PRIORITY_RANK = case({p.value: p.rank for p in Priority}, value=WorkItem.priority)


@dataclass(frozen=True, slots=True)
class TicketScope:
    org_id: uuid.UUID
    space_ids: Select[uuid.UUID]  # the spaces where the actor may read tickets (SQL)


@dataclass(frozen=True, slots=True)
class ParentRef:
    id: uuid.UUID
    number: int
    title: str
    kind: TicketKind


@dataclass(frozen=True, slots=True)
class TicketView:
    """A ticket with what showing it needs: its status, parent, people's names and
    (filled in by the services, `base.with_tags`) its tags."""

    ticket: WorkItem
    status: TicketStatus
    parent: ParentRef | None
    assignee_name: str | None
    reporter_name: str | None
    tags: tuple[Tag, ...] = ()


def _sort_key(sort: Sort) -> ColumnElement[object]:
    if sort == Sort.UPDATED:
        return WorkItem.updated_at  # type: ignore[return-value]
    if sort == Sort.DUE:
        return func.coalesce(WorkItem.due_on, LAST_DAY)
    return PRIORITY_RANK


def _tagged(tag_id: uuid.UUID) -> Select[uuid.UUID]:
    """The tickets carrying the tag (SQL)."""
    return select(Tagging.subject_id).where(
        Tagging.subject_type == SubjectType.TICKET, Tagging.tag_id == tag_id
    )


class TicketRepository:
    def __init__(self, session: AsyncSession, scope: TicketScope) -> None:
        self.session = session
        self.scope = scope

    def _visible(self) -> ColumnElement[bool]:
        return and_(
            WorkItem.org_id == self.scope.org_id, WorkItem.space_id.in_(self.scope.space_ids)
        )

    async def next_number(self) -> int:
        """The organisation's next ticket number; the counter row stays locked until
        the transaction ends, so concurrent creations take turns."""
        stmt = (
            insert(TicketCounter)
            .values(org_id=self.scope.org_id, last_number=1)
            .on_conflict_do_update(
                index_elements=["org_id"],
                set_={"last_number": TicketCounter.last_number + 1},
            )
            .returning(TicketCounter.last_number)
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def add(self, ticket: WorkItem) -> WorkItem:
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    async def by_number(self, number: int, *, lock: bool = False) -> WorkItem | None:
        """The ticket if the actor may see it; with `lock`, as committed now and locked
        until the transaction ends."""
        stmt = (
            select(WorkItem)
            .where(self._visible(), WorkItem.number == number)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def parent_in(self, space_id: uuid.UUID, parent_id: uuid.UUID) -> WorkItem | None:
        """Ticket `parent_id` of the space, as committed now, held (`FOR SHARE`) until
        the transaction ends; None if the space has no such ticket."""
        stmt = (
            select(WorkItem)
            .where(self._visible(), WorkItem.space_id == space_id, WorkItem.id == parent_id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def child_kinds(self, ticket_id: uuid.UUID) -> set[TicketKind]:
        stmt = select(WorkItem.kind).where(WorkItem.parent_id == ticket_id).distinct()
        return {TicketKind(kind) for kind in await self.session.scalars(stmt)}

    async def children_counts(self, ticket_id: uuid.UUID) -> dict[StatusCategory, int]:
        stmt = (
            select(TicketStatus.category, func.count())
            .select_from(WorkItem)
            .join(TicketStatus, TicketStatus.id == WorkItem.status_id)
            .where(WorkItem.parent_id == ticket_id)
            .group_by(TicketStatus.category)
        )
        return {StatusCategory(c): int(n) for c, n in await self.session.execute(stmt)}

    async def assignable(self, space_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Whether the person is active in the organisation and may read tickets in
        the space. One statement, and the same answer (False) for nobody, someone
        elsewhere and someone without access."""
        reads = person_holds_role(
            literal(space_id, PG_UUID(as_uuid=True)), SPACE_ACTION_MIN_ROLE[Action.TICKET_READ]
        )
        stmt = select(exists().where(User.org_id == self.scope.org_id, User.id == user_id, reads))
        return bool(await self.session.scalar(stmt))

    def _views(self) -> ViewSelect:
        parent = aliased(WorkItem)
        assignee = aliased(User)
        reporter = aliased(User)
        return (
            select(
                WorkItem,
                TicketStatus,
                parent.id,
                parent.number,
                parent.title,
                parent.kind,
                assignee.name,
                reporter.name,
            )
            .join(TicketStatus, TicketStatus.id == WorkItem.status_id)
            .outerjoin(parent, parent.id == WorkItem.parent_id)
            .outerjoin(
                assignee,
                and_(
                    WorkItem.assignee_type == PrincipalType.USER,
                    assignee.id == WorkItem.assignee_id,
                    assignee.org_id == WorkItem.org_id,
                ),
            )
            .outerjoin(
                reporter,
                and_(reporter.id == WorkItem.reporter_id, reporter.org_id == WorkItem.org_id),
            )
            .where(self._visible())
        )

    @staticmethod
    def _view(row: Sequence[object]) -> TicketView:
        ticket, status, p_id, p_number, p_title, p_kind, assignee, reporter = row
        assert isinstance(ticket, WorkItem) and isinstance(status, TicketStatus)
        parent = None
        if isinstance(p_id, uuid.UUID):
            parent = ParentRef(p_id, int(str(p_number)), str(p_title), TicketKind(str(p_kind)))
        return TicketView(
            ticket,
            status,
            parent,
            str(assignee) if assignee is not None else None,
            str(reporter) if reporter is not None else None,
        )

    async def view(self, ticket_id: uuid.UUID) -> TicketView | None:
        stmt = self._views().where(WorkItem.id == ticket_id)
        stmt = stmt.execution_options(populate_existing=True)
        row = (await self.session.execute(stmt)).first()
        return self._view(row) if row is not None else None

    async def page(
        self, filters: Filters, sort: Sort, after: Position | None, limit: int
    ) -> list[TicketView]:
        """A page of the visible tickets that pass `filters`, in `sort` order."""
        stmt = self._filtered(self._views(), filters).options(defer(WorkItem.description_md))
        if sort == Sort.NUMBER:
            if after is not None:
                stmt = stmt.where(WorkItem.number < after.number)
            stmt = stmt.order_by(WorkItem.number.desc())
        elif sort == Sort.DUE:
            key = _sort_key(sort)
            if after is not None:
                stmt = stmt.where(
                    tuple_(key, WorkItem.number)
                    > tuple_(literal(after.value), literal(after.number))
                )
            stmt = stmt.order_by(key.asc(), WorkItem.number.asc())
        else:
            key = _sort_key(sort)
            if after is not None:
                stmt = stmt.where(
                    tuple_(key, WorkItem.number)
                    < tuple_(literal(after.value), literal(after.number))
                )
            stmt = stmt.order_by(key.desc(), WorkItem.number.desc())
        rows = await self.session.execute(stmt.limit(limit))
        return [self._view(row) for row in rows]

    def _filtered[S: Select[*tuple[Any, ...]]](self, stmt: S, f: Filters) -> S:
        """`stmt` (over `work_item`; joined with its status for a category filter)
        narrowed by the filters."""
        if f.space_id is not None:
            stmt = stmt.where(WorkItem.space_id == f.space_id)
        if f.status_categories:
            stmt = stmt.where(TicketStatus.category.in_(f.status_categories))
        if f.status_id is not None:
            stmt = stmt.where(WorkItem.status_id == f.status_id)
        if f.assignee_id is not None:
            stmt = stmt.where(
                WorkItem.assignee_type == PrincipalType.USER, WorkItem.assignee_id == f.assignee_id
            )
        if f.unassigned:
            stmt = stmt.where(WorkItem.assignee_id.is_(None))
        if f.reporter_id is not None:
            stmt = stmt.where(
                WorkItem.reporter_type == PrincipalType.USER, WorkItem.reporter_id == f.reporter_id
            )
        if f.kind is not None:
            stmt = stmt.where(WorkItem.kind == f.kind)
        if f.priority is not None:
            stmt = stmt.where(WorkItem.priority == f.priority)
        if f.parent_id is not None:
            stmt = stmt.where(WorkItem.parent_id == f.parent_id)
        if f.due_before is not None:
            stmt = stmt.where(WorkItem.due_on < f.due_before)
        if f.epic_id is not None:
            stories = select(WorkItem.id).where(WorkItem.parent_id == f.epic_id)
            stmt = stmt.where(or_(WorkItem.parent_id == f.epic_id, WorkItem.parent_id.in_(stories)))
        if f.sprint_id is not None:
            stmt = stmt.where(WorkItem.sprint_id == f.sprint_id)
        if f.backlog:
            stmt = stmt.where(WorkItem.sprint_id.is_(None))
        for tag_id in f.tag_ids:  # every one of them
            stmt = stmt.where(WorkItem.id.in_(_tagged(tag_id)))
        if f.q is not None:
            query = func.websearch_to_tsquery(_GERMAN, f.q).op("||")(
                func.websearch_to_tsquery(_SIMPLE, f.q)
            )
            stmt = stmt.where(WorkItem.search_tsv.op("@@")(query))
        return stmt
