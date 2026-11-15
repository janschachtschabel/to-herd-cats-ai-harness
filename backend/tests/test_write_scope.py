"""`write_scope` on an actor (plan M6 decision 5): outside the spaces it lists, the
actor may still read what its rights and read scope allow, but do nothing that
writes, posting in a channel included, admins too. The core applies it to any actor
without knowing who set it or why (`tests/test_read_scope.py` for the read scope)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, my_roles, require, space_ids_with
from app.core.access_repository import remembered_facts
from app.core.actor import ReadScope, WriteScope
from app.core.errors import Forbidden
from app.core.permissions import SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.spaces.models import Space, SpaceKind
from app.modules.users.models import User
from tests.factories_spaces import MakeSpace


def _actor(user: User, writes: set[object] | None, reads: dict | None = None) -> Actor:  # type: ignore[type-arg]
    return Actor(
        user.org_id,
        Principal.user(user.id),
        user.system_role,
        frozenset(),
        ReadScope.of(reads) if reads is not None else None,
        WriteScope.of(writes) if writes is not None else None,  # type: ignore[arg-type]
    )


async def _ids(session: AsyncSession, stmt: object) -> set[object]:
    return set(await session.scalars(select(Space.id).where(Space.id.in_(stmt))))  # type: ignore[arg-type]


async def test_outside_the_write_scope_one_reads_but_never_writes(
    session: AsyncSession, make_user, make_space: MakeSpace
) -> None:
    person = await make_user(SystemRole.MEMBER)
    a = await make_space(SpaceKind.TEAM, members=[(person, SpaceRole.ADMIN)])
    b = await make_space(SpaceKind.TEAM, members=[(person, SpaceRole.ADMIN)])
    actor = _actor(person, {a.id})
    for action in (Action.PAGE_EDIT, Action.TICKET_CREATE, Action.CHANNEL_POST):
        assert await can(session, actor, action, a.id), action
        assert not await can(session, actor, action, b.id), action
    assert await can(session, actor, Action.SPACE_READ, b.id)
    assert await can(session, actor, Action.TICKET_READ, b.id)
    with pytest.raises(Forbidden):
        await require(session, actor, Action.PAGE_EDIT, b.id)
    assert await _ids(session, space_ids_with(actor, Action.PAGE_EDIT)) == {a.id}
    assert {a.id, b.id} <= await _ids(session, space_ids_with(actor, Action.TICKET_READ))
    assert await my_roles(session, actor, [a.id, b.id]) == {
        a.id: SpaceRole.ADMIN,
        b.id: SpaceRole.VIEWER,
    }


async def test_admins_are_held_to_it_too(
    session: AsyncSession, make_user, make_space: MakeSpace
) -> None:
    admin = await make_user(SystemRole.ADMIN)
    a = await make_space(SpaceKind.TEAM)
    b = await make_space(SpaceKind.OPEN)
    actor = _actor(admin, {a.id})
    assert await can(session, actor, Action.PAGE_EDIT, a.id)
    assert not await can(session, actor, Action.CHANNEL_POST, b.id)
    assert not await can(session, actor, Action.SPACE_MANAGE, b.id)
    assert await _ids(session, space_ids_with(actor, Action.PAGE_EDIT)) == {a.id}


async def test_the_write_scope_never_adds_a_right(
    session: AsyncSession, make_user, make_space: MakeSpace
) -> None:
    person = await make_user(SystemRole.MEMBER)
    a = await make_space(SpaceKind.TEAM, members=[(person, SpaceRole.VIEWER)])
    hidden = await make_space(SpaceKind.TEAM)
    actor = _actor(person, {a.id, hidden.id}, reads={a.id: SpaceRole.ADMIN})
    assert not await can(session, actor, Action.PAGE_EDIT, a.id)  # the person is a viewer
    assert not await can(session, actor, Action.SPACE_READ, hidden.id)
    assert await _ids(session, space_ids_with(actor, Action.PAGE_EDIT)) == set()


async def test_an_empty_write_scope_writes_nowhere_and_none_is_no_limit(
    session: AsyncSession, make_user, make_space: MakeSpace
) -> None:
    person = await make_user(SystemRole.MEMBER)
    a = await make_space(SpaceKind.TEAM, members=[(person, SpaceRole.EDITOR)])
    assert not await can(session, _actor(person, set()), Action.PAGE_EDIT, a.id)
    assert await can(session, _actor(person, None), Action.PAGE_EDIT, a.id)


async def test_remembered_facts_keep_write_scopes_apart(
    session: AsyncSession, make_user, make_space: MakeSpace
) -> None:
    person = await make_user(SystemRole.MEMBER)
    a = await make_space(SpaceKind.TEAM, members=[(person, SpaceRole.EDITOR)])
    with remembered_facts(session):
        assert await can(session, _actor(person, None), Action.PAGE_EDIT, a.id)
        assert not await can(session, _actor(person, set()), Action.PAGE_EDIT, a.id)
