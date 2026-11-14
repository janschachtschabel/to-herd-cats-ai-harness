"""`read_scope` on an actor (spec 5.6): the check and every list filter see only the
spaces it lists, and the actor's role there is capped by it, admins included. The core
applies it to any actor without knowing who set it or why."""

import dataclasses

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import (
    Action,
    Actor,
    can,
    my_roles,
    require,
    space_ids_with,
    space_role,
    visible_space_ids,
)
from app.core.actor import ReadScope
from app.core.errors import NotFound
from app.core.permissions import SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.spaces.models import Space, SpaceKind
from app.modules.users.models import User
from tests.factories_spaces import MakeSpace


def _actor(user: User, scope: dict | None = None) -> Actor:  # type: ignore[type-arg]
    return Actor(
        user.org_id,
        Principal.user(user.id),
        user.system_role,
        frozenset(),
        ReadScope.of(scope) if scope is not None else None,
    )


async def _ids(session: AsyncSession, stmt: object) -> set[object]:
    return set(await session.scalars(select(Space.id).where(Space.id.in_(stmt))))  # type: ignore[arg-type]


async def test_a_space_outside_the_scope_is_not_there(
    session: AsyncSession, make_user, make_space: MakeSpace
) -> None:
    person = await make_user(SystemRole.MEMBER)
    a = await make_space(SpaceKind.TEAM, members=[(person, SpaceRole.EDITOR)])
    b = await make_space(SpaceKind.TEAM, members=[(person, SpaceRole.EDITOR)])
    actor = _actor(person, {a.id: SpaceRole.VIEWER})
    assert await can(session, actor, Action.SPACE_READ, a.id)
    assert not await can(session, actor, Action.SPACE_READ, b.id)
    with pytest.raises(NotFound):
        await require(session, actor, Action.SPACE_READ, b.id)
    assert await _ids(session, visible_space_ids(actor)) == {a.id}


async def test_the_role_in_a_listed_space_is_capped(
    session: AsyncSession, make_user, make_space: MakeSpace
) -> None:
    person = await make_user(SystemRole.MEMBER)
    a = await make_space(SpaceKind.TEAM, members=[(person, SpaceRole.EDITOR)])
    b = await make_space(SpaceKind.TEAM, members=[(person, SpaceRole.EDITOR)])
    actor = _actor(person, {a.id: SpaceRole.VIEWER, b.id: SpaceRole.ADMIN})
    assert not await can(session, actor, Action.PAGE_EDIT, a.id)
    assert await can(session, actor, Action.PAGE_EDIT, b.id)  # the person's own role
    assert not await can(session, actor, Action.SPACE_MANAGE, b.id)  # ... caps the scope
    assert await space_role(session, actor, a.id) == SpaceRole.VIEWER
    assert await _ids(session, space_ids_with(actor, Action.PAGE_EDIT)) == {b.id}
    assert await my_roles(session, actor, [a.id, b.id]) == {
        a.id: SpaceRole.VIEWER,
        b.id: SpaceRole.EDITOR,
    }


async def test_the_scope_never_adds_what_the_person_lacks(
    session: AsyncSession, make_user, make_space: MakeSpace
) -> None:
    person = await make_user(SystemRole.MEMBER)
    a = await make_space(SpaceKind.TEAM)
    actor = _actor(person, {a.id: SpaceRole.ADMIN})
    assert not await can(session, actor, Action.SPACE_READ, a.id)
    assert await _ids(session, visible_space_ids(actor)) == set()


async def test_admins_are_capped_too(
    session: AsyncSession, make_user, make_space: MakeSpace
) -> None:
    admin = await make_user(SystemRole.ADMIN)
    a = await make_space(SpaceKind.TEAM)
    b = await make_space(SpaceKind.TEAM)
    actor = _actor(admin, {a.id: SpaceRole.VIEWER})
    assert await can(session, actor, Action.SPACE_READ, a.id)
    assert not await can(session, actor, Action.PAGE_EDIT, a.id)
    assert not await can(session, actor, Action.SPACE_READ, b.id)
    assert await my_roles(session, actor, [a.id]) == {a.id: SpaceRole.VIEWER}
    assert await _ids(session, space_ids_with(actor, Action.PAGE_EDIT)) == set()


async def test_an_empty_scope_sees_nothing(
    session: AsyncSession, make_user, make_space: MakeSpace
) -> None:
    person = await make_user(SystemRole.MEMBER)
    await make_space(SpaceKind.OPEN)
    actor = _actor(person, {})
    assert await _ids(session, visible_space_ids(actor)) == set()
    assert dataclasses.replace(actor, read_scope=None) != actor
