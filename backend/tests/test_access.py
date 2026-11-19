"""The one permission check (`app.core.access`): `can`, `require`, `space_role` and
`visible_space_ids` against a matrix of system role x space kind x membership."""

import itertools
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import event, update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.access import (
    Action,
    Actor,
    actor_for,
    can,
    member_space_ids,
    require,
    space_ids_with,
    space_role,
    visible_space_ids,
)
from app.core.errors import Forbidden, NotFound, Unauthorized
from app.core.permissions import SPACE_ACTION_MIN_ROLE, SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.auth.context import AuthContext
from app.modules.groups.repository import GroupRepository
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository
from app.modules.users.models import User
from tests.factories_spaces import personal_space_of

ROLES = [SystemRole.OWNER, SystemRole.ADMIN, SystemRole.MEMBER, SystemRole.GUEST]
KINDS = [SpaceKind.OPEN, SpaceKind.TEAM, SpaceKind.PERSONAL]
# How the person holds the space: (direct role, role of a group they are in).
MODES: dict[str, tuple[SpaceRole | None, SpaceRole | None]] = {
    "none": (None, None),
    "direct": (SpaceRole.VIEWER, None),
    "group": (None, SpaceRole.EDITOR),
    "both": (SpaceRole.VIEWER, SpaceRole.ADMIN),  # the higher one counts
}


async def actor_of(session: AsyncSession, user: User) -> Actor:
    return await actor_for(session, AuthContext(user=user))


@dataclass
class Case:
    holder: User  # whose membership the space was made for
    kind: SpaceKind
    mode: str
    space: Space


@pytest.fixture
async def actors_and_spaces(
    session: AsyncSession, org: Organization, make_user, make_group
) -> tuple[list[User], list[Case]]:
    """One person per system role, each in a group of their own; for each of them one
    space per kind and membership mode. Every person sees everyone else's spaces too."""
    spaces = SpaceRepository(session)
    people = [await make_user(role) for role in ROLES]
    cases: list[Case] = []
    for person in people:
        group = await make_group(members=[person])
        for kind, mode in itertools.product(KINDS, MODES):
            if kind == SpaceKind.PERSONAL:  # someone else's, the person joins it below
                space = await personal_space_of(session, await make_user())
            else:
                space = await spaces.add(Space(org_id=org.id, kind=kind, name="x"))
            direct, via_group = MODES[mode]
            if direct:
                await spaces.set_member(space.id, Principal.user(person.id), direct)
            if via_group:
                await spaces.set_member(space.id, Principal.group(group.id), via_group)
            cases.append(Case(person, kind, mode, space))
    return people, cases


def _expected_role(person: User, case: Case) -> SpaceRole | None:
    direct, via_group = MODES[case.mode] if case.holder is person else (None, None)
    floor = (
        SpaceRole.VIEWER
        if case.kind == SpaceKind.OPEN and person.system_role != SystemRole.GUEST
        else None
    )
    return max((r for r in (direct, via_group, floor) if r is not None), default=None)


async def test_visible_space_ids_matches_can(
    session: AsyncSession, actors_and_spaces: tuple[list[User], list[Case]]
) -> None:
    """The SQL filter and the single check never disagree, and both follow the rules."""
    people, cases = actors_and_spaces
    for person in people:
        actor = await actor_of(session, person)
        visible: set[UUID] = set((await session.scalars(visible_space_ids(actor))).all())
        for case in cases:
            role = _expected_role(person, case)
            readable = actor.is_admin or role is not None
            manageable = actor.is_admin or role == SpaceRole.ADMIN
            sid = case.space.id
            label = (person.system_role, case.kind, case.mode, case.holder is person)
            assert (sid in visible) == readable, label
            assert await can(session, actor, Action.SPACE_READ, sid) == readable, label
            assert await can(session, actor, Action.SPACE_MANAGE, sid) == manageable, label
            assert await space_role(session, actor, sid) == role, label


async def test_member_space_ids_leave_out_what_only_admin_power_opens(
    session: AsyncSession, actors_and_spaces: tuple[list[User], list[Case]]
) -> None:
    """The list rule of calendars (plan M10 decision 3, C1): the spaces where the
    person holds a role of her own (directly, through a group, or the open floor);
    admins and owners get no space from their admin power."""
    people, cases = actors_and_spaces
    for person in people:
        actor = await actor_of(session, person)
        ids: set[UUID] = set((await session.scalars(member_space_ids(actor))).all())
        for case in cases:
            label = (person.system_role, case.kind, case.mode, case.holder is person)
            assert (case.space.id in ids) == (_expected_role(person, case) is not None), label


async def test_space_ids_with_matches_can(
    session: AsyncSession, actors_and_spaces: tuple[list[User], list[Case]]
) -> None:
    """The SQL filter for one space action agrees with the single check, per action."""
    people, cases = actors_and_spaces
    for person in people:
        actor = await actor_of(session, person)
        for action in SPACE_ACTION_MIN_ROLE:
            ids: set[UUID] = set((await session.scalars(space_ids_with(actor, action))).all())
            for case in cases:
                label = (person.system_role, case.kind, case.mode, action)
                expected = await can(session, actor, action, case.space.id)
                assert (case.space.id in ids) == expected, label


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (SystemRole.OWNER, set(Action)),
        (SystemRole.ADMIN, set(Action)),
        (SystemRole.MEMBER, {Action.SPACE_CREATE}),
        (SystemRole.GUEST, set()),
    ],
)
async def test_system_actions_follow_the_system_role(
    session: AsyncSession, make_user, role: SystemRole, allowed: set[Action]
) -> None:
    actor = await actor_of(session, await make_user(role))
    for action in (Action.SPACE_CREATE, Action.USER_MANAGE, Action.GROUP_MANAGE, Action.AUDIT_READ):
        assert await can(session, actor, action) == (action in allowed), action


async def test_space_actions_need_a_space(session: AsyncSession, owner_user: User) -> None:
    actor = await actor_of(session, owner_user)
    assert not await can(session, actor, Action.SPACE_READ)
    with pytest.raises(Forbidden):
        await require(session, actor, Action.SPACE_MANAGE)


async def test_group_role_counts_and_is_revoked_on_removal(
    session: AsyncSession, member: User, team_space: Space, group
) -> None:
    groups, spaces = GroupRepository(session), SpaceRepository(session)
    await groups.add_member(group.id, Principal.user(member.id))
    await spaces.set_member(team_space.id, Principal.group(group.id), SpaceRole.EDITOR)
    assert await space_role(session, await actor_of(session, member), team_space.id) == (
        SpaceRole.EDITOR
    )
    await groups.remove_member(group.id, Principal.user(member.id))
    actor = await actor_of(session, member)
    assert await space_role(session, actor, team_space.id) is None
    assert not await can(session, actor, Action.SPACE_READ, team_space.id)


async def test_direct_role_and_group_role_take_the_higher(
    session: AsyncSession, member: User, team_space: Space, group_with_member
) -> None:
    spaces = SpaceRepository(session)
    await spaces.set_member(team_space.id, Principal.user(member.id), SpaceRole.VIEWER)
    await spaces.set_member(team_space.id, Principal.group(group_with_member.id), "editor")
    assert await space_role(session, await actor_of(session, member), team_space.id) == (
        SpaceRole.EDITOR
    )


async def test_require_hides_invisible_spaces_and_forbids_the_rest(
    session: AsyncSession, member: User, team_space: Space, open_space: Space
) -> None:
    actor = await actor_of(session, member)
    for space_id in (team_space.id, uuid7()):
        with pytest.raises(NotFound) as hidden:
            await require(session, actor, Action.SPACE_MANAGE, space_id)
        assert hidden.value.code == "space.not_found"
    await require(session, actor, Action.SPACE_READ, open_space.id)
    with pytest.raises(Forbidden) as denied:
        await require(session, actor, Action.SPACE_MANAGE, open_space.id)
    assert denied.value.code == "auth.permission_denied"
    with pytest.raises(Forbidden):
        await require(session, actor, Action.USER_MANAGE)


async def test_other_organisations_spaces_do_not_exist_for_their_admins(
    session: AsyncSession, owner_user: User
) -> None:
    elsewhere = Organization(name="Elsewhere")
    session.add(elsewhere)
    await session.flush()
    foreign = Space(org_id=elsewhere.id, kind=SpaceKind.OPEN, name="F")
    session.add(foreign)
    await session.flush()
    actor = await actor_of(session, owner_user)
    assert not await can(session, actor, Action.SPACE_READ, foreign.id)
    assert foreign.id not in set((await session.scalars(visible_space_ids(actor))).all())
    with pytest.raises(NotFound):
        await require(session, actor, Action.SPACE_READ, foreign.id)


async def test_a_deactivated_person_gets_no_actor(session: AsyncSession, make_user) -> None:
    gone = await make_user(SystemRole.ADMIN, is_active=False)
    with pytest.raises(Unauthorized):
        await actor_of(session, gone)


async def test_role_and_activity_are_read_live(
    session: AsyncSession, make_user, team_space: Space
) -> None:
    """An actor that outlives a change (a long request, later an agent run) gets the
    change at its next check: demoted or deactivated means fewer rights at once."""
    admin = await make_user(SystemRole.ADMIN)
    actor = await actor_of(session, admin)
    assert await can(session, actor, Action.SPACE_MANAGE, team_space.id)
    await session.execute(
        update(User).where(User.id == admin.id).values(system_role=SystemRole.MEMBER)
    )
    assert not await can(session, actor, Action.SPACE_MANAGE, team_space.id)
    assert not await can(session, actor, Action.USER_MANAGE)
    assert team_space.id not in set((await session.scalars(visible_space_ids(actor))).all())

    await session.execute(update(User).where(User.id == admin.id).values(is_active=False))
    personal = await personal_space_of(session, admin)  # still holds the admin role there
    assert not await can(session, actor, Action.SPACE_READ, personal.id)
    assert not await can(session, actor, Action.SPACE_CREATE)
    assert set((await session.scalars(visible_space_ids(actor))).all()) == set()


@contextmanager
def _counting(sync_conn: object) -> Iterator[list[str]]:
    statements: list[str] = []

    def _count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(sync_conn, "before_cursor_execute", _count)
    try:
        yield statements
    finally:
        event.remove(sync_conn, "before_cursor_execute", _count)


async def test_each_check_is_one_query(
    session: AsyncSession, member: User, team_space: Space, group_with_member
) -> None:
    await SpaceRepository(session).set_member(
        team_space.id, Principal.group(group_with_member.id), SpaceRole.ADMIN
    )
    actor = await actor_of(session, member)
    sync_conn = (await session.connection()).sync_connection
    checks = (
        lambda: can(session, actor, Action.SPACE_MANAGE, team_space.id),
        lambda: can(session, actor, Action.SPACE_CREATE),
        lambda: space_role(session, actor, team_space.id),
        lambda: require(session, actor, Action.SPACE_MANAGE, team_space.id),
    )
    for check in checks:
        with _counting(sync_conn) as statements:
            await check()
        assert len(statements) == 1, statements


def test_space_roles_are_ordered() -> None:
    assert SpaceRole.VIEWER < SpaceRole.EDITOR < SpaceRole.MODERATOR < SpaceRole.ADMIN
    assert max(SpaceRole.ADMIN, SpaceRole.EDITOR) == SpaceRole.ADMIN  # not alphabetical
    assert SpaceRole.ADMIN >= SpaceRole.ADMIN > SpaceRole.VIEWER
