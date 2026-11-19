"""The calendars' "who belongs to a space" asked in two ways that must agree (review
M10 task 3a, R3a-12): per actor (`access.member_space_ids`, for lists) and for many
people at once (`person_reads_space(..., by_admin_power=False)`, for the recipients of
`calendar.changed`). Neither grows with admin power. A matrix of people (own and group
membership, admins in and out, guests in and out of an open space, a deactivated
member, someone of another organisation) and spaces holds them to the same answers."""

import itertools

from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import member_space_ids
from app.core.access_repository import person_reads_space
from app.core.actor import Actor
from app.core.permissions import SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.groups.repository import GroupRepository
from app.modules.orgs.models import Organization
from app.modules.spaces.models import SpaceKind
from app.modules.users.models import User
from tests.factories_spaces import personal_space_of


async def _actor(session: AsyncSession, user: User) -> Actor:
    groups = await GroupRepository(session).group_ids_for(Principal.user(user.id))
    return Actor(user.org_id, Principal.user(user.id), SystemRole(user.system_role), groups)


async def test_members_asked_per_person_and_at_once_agree(
    session: AsyncSession, make_user, make_space, make_group, owner_user: User
) -> None:
    people = {
        "owner": owner_user,
        "admin": await make_user(SystemRole.ADMIN),
        "admin_in": await make_user(SystemRole.ADMIN),
        "member": await make_user(),
        "direct": await make_user(),
        "grouped": await make_user(),
        "guest": await make_user(SystemRole.GUEST),
        "guest_in": await make_user(SystemRole.GUEST),
        "inactive": await make_user(),
    }
    elsewhere = Organization(name="Andere")
    session.add(elsewhere)
    await session.flush()
    people["stranger"] = await make_user(organization=elsewhere)
    group = await make_group(members=[people["grouped"]])
    team = await make_space(
        SpaceKind.TEAM,
        members=[
            (people["direct"], SpaceRole.VIEWER),
            (group, SpaceRole.EDITOR),
            (people["guest_in"], SpaceRole.VIEWER),
            (people["inactive"], SpaceRole.ADMIN),
            (people["admin_in"], SpaceRole.VIEWER),
        ],
    )
    open_ = await make_space(SpaceKind.OPEN, members=[(people["guest_in"], SpaceRole.VIEWER)])
    grouped_open = await make_space(SpaceKind.OPEN, members=[(group, SpaceRole.VIEWER)])
    personal = await personal_space_of(session, people["member"])
    people["inactive"].is_active = False
    await session.flush()

    spaces = {"team": team.id, "open": open_.id, "grouped_open": grouped_open.id}
    spaces["personal"] = personal.id
    names = {user.id: name for name, user in people.items()}
    at_once: dict[str, set[str]] = {}
    for label, space_id in spaces.items():
        stmt = select(User.id).where(person_reads_space(literal(space_id), by_admin_power=False))
        at_once[label] = {names[u] for u in (await session.scalars(stmt)).all() if u in names}
    for (label, space_id), (name, user) in itertools.product(spaces.items(), people.items()):
        actor = await _actor(session, user)
        per_person = space_id in set((await session.scalars(member_space_ids(actor))).all())
        assert per_person == (name in at_once[label]), (label, name)
    assert at_once["team"] == {"direct", "grouped", "guest_in", "admin_in"}
    assert at_once["open"] == {"owner", "admin", "admin_in", "member", "direct", "grouped"} | {
        "guest_in"
    }
    assert at_once["personal"] == {"member"}
