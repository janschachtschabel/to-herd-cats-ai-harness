"""What the database guarantees about tickets (plan M4 task 1), whatever code writes:
numbers unique per organisation, parent and status in the ticket's space, the default
statuses of spaces that exist when the migration runs."""

import importlib.util
from types import ModuleType

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.migrations import MIGRATIONS_DIR
from app.modules.spaces.models import Space
from app.modules.tickets.models import TicketStatus
from app.modules.users.models import User
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import ticket_row


def _migration() -> ModuleType:
    (path,) = (MIGRATIONS_DIR / "versions").glob("*_m4_tickets.py")
    spec = importlib.util.spec_from_file_location("m4_tickets", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _refused(session: AsyncSession, statement: str, **params: object) -> str:
    """The statement fails; the error's text (savepoint, so the test goes on)."""
    with pytest.raises((IntegrityError, DBAPIError)) as caught:
        async with session.begin_nested():
            await session.execute(text(statement), params)
    return str(caught.value)


async def test_the_migration_gives_spaces_without_statuses_the_defaults(
    session: AsyncSession, open_space: Space, team_space: Space
) -> None:
    await session.execute(delete(TicketStatus).where(TicketStatus.space_id == open_space.id))
    await session.execute(text(_migration().BACKFILL))
    rows = await session.execute(
        select(TicketStatus.space_id, func.count())
        .where(TicketStatus.space_id.in_([open_space.id, team_space.id]))
        .group_by(TicketStatus.space_id)
    )
    assert dict(rows.all()) == {open_space.id: 5, team_space.id: 5}  # none twice


async def test_numbers_are_unique_per_organisation(
    session: AsyncSession, open_space: Space, team_space: Space, member: User
) -> None:
    await ticket_row(session, open_space, member, number=7)
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await ticket_row(session, team_space, member, number=7)


async def test_a_parent_lives_in_the_same_space(
    session: AsyncSession, open_space: Space, team_space: Space, member: User
) -> None:
    epic = await ticket_row(session, open_space, member, kind="epic")
    child = await ticket_row(session, team_space, member)
    error = await _refused(
        session,
        "UPDATE work_item SET parent_id = :parent WHERE id = :child",
        parent=epic.id,
        child=child.id,
    )
    assert "work_item_parent_other_space" in error
    error = await _refused(
        session, "UPDATE work_item SET parent_id = id WHERE id = :child", child=child.id
    )
    assert "parent_not_self" in error or "work_item_parent" in error


async def test_a_status_belongs_to_the_tickets_space(
    session: AsyncSession, open_space: Space, team_space: Space, member: User
) -> None:
    foreign = await session.scalar(
        select(TicketStatus.id).where(TicketStatus.space_id == team_space.id).limit(1)
    )
    item = await ticket_row(session, open_space, member)
    error = await _refused(
        session,
        "UPDATE work_item SET status_id = :status WHERE id = :id",
        status=foreign,
        id=item.id,
    )
    assert "work_item_status_other_space" in error


async def test_an_assignee_is_a_person_or_nobody(
    session: AsyncSession, open_space: Space, member: User
) -> None:
    item = await ticket_row(session, open_space, member)
    for values in ("'user', NULL", "NULL, :person", "'group', :person"):
        error = await _refused(
            session,
            f"UPDATE work_item SET (assignee_type, assignee_id) = ({values}) WHERE id = :id",
            person=member.id,
            id=item.id,
        )
        assert "ck_work_item_assignee" in error, values


async def test_statuses_go_with_their_space(
    session: AsyncSession, make_space: MakeSpace, member: User
) -> None:
    space = await make_space("open", "Weg")
    await ticket_row(session, space, member)
    await session.execute(delete(Space).where(Space.id == space.id))
    left = await session.scalar(
        select(func.count()).select_from(TicketStatus).where(TicketStatus.space_id == space.id)
    )
    assert left == 0
