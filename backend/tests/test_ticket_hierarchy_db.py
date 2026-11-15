"""The ticket hierarchy held by the database (review M4 P7): not even a write past the
services makes a ticket its own parent, puts it below a ticket of another space or
of a kind that may not sit above it, or changes a kind (or a space) so that its
children no longer fit. With the kinds strictly ordered (epic > story > task/bug) a
cycle is then impossible. The open/done minimum of statuses stays with the service."""

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket


async def _refused(session: AsyncSession, statement: str, **params: Any) -> str:
    with pytest.raises(DBAPIError) as refused:
        async with session.begin_nested():
            await session.execute(text(statement), params)
    return str(refused.value.orig)


async def _set(session: AsyncSession, ticket: dict[str, Any], **values: Any) -> str:
    sets = ", ".join(f"{name} = :{name}" for name in values)
    return await _refused(
        session,
        f"UPDATE work_item SET {sets} WHERE id = :id",  # noqa: S608 -- names are ours
        id=uuid.UUID(ticket["id"]),
        **{k: uuid.UUID(v) if k.endswith("_id") else v for k, v in values.items()},
    )


async def test_the_database_keeps_the_hierarchy(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    epic = await new_ticket(desk.editor, desk.space_id, "E", kind="epic")
    story = await new_ticket(desk.editor, desk.space_id, "S", kind="story", parent_id=epic["id"])
    other = await new_ticket(desk.editor, desk.space_id, "S2", kind="story")
    task = await new_ticket(desk.editor, desk.space_id, "T", kind="task", parent_id=story["id"])
    elsewhere_space = await make_space("team", "Anders")
    elsewhere = await new_ticket(desk.admin, elsewhere_space.id, "E2", kind="epic")

    assert "work_item_parent_self" in await _set(session, other, parent_id=other["id"])
    # The reviewer's cycle: the epic below its own story.
    assert "work_item_parent_kind" in await _set(session, epic, parent_id=story["id"])
    assert "work_item_parent_kind" in await _set(session, other, parent_id=story["id"])
    assert "work_item_parent_kind" in await _set(session, other, parent_id=task["id"])
    assert "work_item_parent_other_space" in await _set(session, other, parent_id=elsewhere["id"])
    # A kind change that its children (or its own parent) do not allow.
    assert "work_item_children_do_not_fit" in await _set(session, epic, kind="task")
    assert "work_item_children_do_not_fit" in await _set(session, story, kind="bug")
    assert "work_item_parent_kind" in await _set(session, story, kind="epic")
    # A ticket with children does not change space (its children would stay behind).
    assert "work_item_children_do_not_fit" in await _set(
        session, epic, space_id=str(elsewhere_space.id)
    )

    async with session.begin_nested():  # what the rules allow still goes through
        await session.execute(
            text("UPDATE work_item SET parent_id = :p, kind = 'bug' WHERE id = :id"),
            {"p": uuid.UUID(epic["id"]), "id": uuid.UUID(other["id"])},
        )
        await session.execute(
            text("UPDATE work_item SET kind = 'bug' WHERE id = :id"),
            {"id": uuid.UUID(task["id"])},
        )
