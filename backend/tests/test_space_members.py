from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.principal import Principal
from app.modules.groups.models import Group
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space, SpaceMember
from app.modules.spaces.repository import SpaceRepository
from app.modules.users.models import User
from tests.factories_spaces import personal_space_of

SPACES = "/api/spaces"


def _entry(holder: User | Group, role: str) -> dict[str, str]:
    kind = "user" if isinstance(holder, User) else "group"
    return {"member_type": kind, "member_id": str(holder.id), "role": role}


async def _members(client: AsyncClient, space: Space) -> list[dict[str, str]]:
    """The members without their display names (test_client_view checks those)."""
    items = (await client.get(f"{SPACES}/{space.id}/members")).json()["items"]
    return [{k: v for k, v in m.items() if k != "name"} for m in items]


async def test_personal_space_members_are_fixed(
    owner: AsyncClient, member: User, guest: User, session: AsyncSession
) -> None:
    space = await personal_space_of(session, member)
    r = await owner.put(f"{SPACES}/{space.id}/members", json=_entry(guest, "viewer"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "spaces.personal_members_fixed"
    r = await owner.delete(f"{SPACES}/{space.id}/members/user/{member.id}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "spaces.personal_members_fixed"
    assert await _members(owner, space) == [_entry(member, "admin")]


async def test_space_admin_manages_members_but_viewer_cannot(
    member_client: AsyncClient, guest_client: AsyncClient, member: User, guest: User, make_space
) -> None:
    space = await make_space("team", members=[(member, "admin")])
    base = f"{SPACES}/{space.id}/members"
    assert (await guest_client.get(f"{SPACES}/{space.id}")).status_code == 404

    r = await member_client.put(base, json=_entry(guest, "viewer"))
    assert r.status_code == 200 and r.json() == {**_entry(guest, "viewer"), "name": guest.name}
    assert (await guest_client.get(f"{SPACES}/{space.id}")).status_code == 200
    assert {m["member_id"] for m in await _members(guest_client, space)} == {
        str(member.id),
        str(guest.id),
    }
    for response in (
        await guest_client.put(base, json=_entry(guest, "admin")),
        await guest_client.delete(f"{base}/user/{member.id}"),
        await guest_client.patch(f"{SPACES}/{space.id}", json={"name": "x", "version": 1}),
    ):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "auth.permission_denied"

    r = await member_client.put(base, json=_entry(guest, "editor"))  # change of role
    assert r.json()["role"] == "editor"
    assert len(await _members(member_client, space)) == 2
    assert (await member_client.delete(f"{base}/user/{guest.id}")).status_code == 204
    assert (await guest_client.get(f"{SPACES}/{space.id}")).status_code == 404


async def test_a_group_membership_opens_the_space_to_its_people(
    owner: AsyncClient, member_client: AsyncClient, team_space: Space, group_with_member: Group
) -> None:
    base = f"{SPACES}/{team_space.id}/members"
    r = await owner.put(base, json=_entry(group_with_member, "editor"))
    assert r.status_code == 200
    assert (await member_client.get(f"{SPACES}/{team_space.id}")).status_code == 200
    assert (await owner.delete(f"{base}/group/{group_with_member.id}")).status_code == 204
    assert (await member_client.get(f"{SPACES}/{team_space.id}")).status_code == 404


async def test_deleting_a_group_removes_its_space_memberships(
    owner: AsyncClient,
    member_client: AsyncClient,
    make_space,
    group_with_member: Group,
    session: AsyncSession,
) -> None:
    spaces = [await make_space("team", members=[(group_with_member, "viewer")]) for _ in range(2)]
    other_group_space = await make_space("team")
    await SpaceRepository(session).set_member(
        other_group_space.id, Principal.group(uuid7()), "viewer"
    )
    assert (await owner.delete(f"/api/admin/groups/{group_with_member.id}")).status_code == 204
    rows = select(func.count()).select_from(SpaceMember).where(SpaceMember.member_type == "group")
    assert await session.scalar(rows) == 1  # only the other group's
    for space in spaces:
        assert (await member_client.get(f"{SPACES}/{space.id}")).status_code == 404


async def test_deactivated_people_keep_their_memberships(
    owner: AsyncClient, member: User, team_space: Space
) -> None:
    base = f"{SPACES}/{team_space.id}/members"
    await owner.put(base, json=_entry(member, "editor"))
    assert (await owner.post(f"/api/admin/users/{member.id}/deactivate")).status_code == 204
    assert _entry(member, "editor") in await _members(owner, team_space)


async def test_new_members_must_exist_in_the_organisation(
    owner: AsyncClient, team_space: Space, make_user, session: AsyncSession
) -> None:
    elsewhere = Organization(name="Elsewhere")
    session.add(elsewhere)
    await session.flush()
    stranger = await make_user(organization=elsewhere)
    base = f"{SPACES}/{team_space.id}/members"
    for body, code in (
        (_entry(stranger, "viewer"), "users.not_found"),
        ({"member_type": "user", "member_id": str(uuid7()), "role": "viewer"}, "users.not_found"),
        ({"member_type": "group", "member_id": str(uuid7()), "role": "viewer"}, "groups.not_found"),
    ):
        r = await owner.put(base, json=body)
        assert r.status_code == 404 and r.json()["error"]["code"] == code
    for bad in (
        {"member_type": "agent", "member_id": str(uuid7()), "role": "viewer"},
        {"member_type": "user", "member_id": str(stranger.id), "role": "owner"},
    ):
        assert (await owner.put(base, json=bad)).status_code == 422


async def test_removing_a_non_member_is_404(owner: AsyncClient, team_space, member) -> None:
    r = await owner.delete(f"{SPACES}/{team_space.id}/members/user/{member.id}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "spaces.member_not_found"


async def test_invisible_space_members_are_404(
    member_client: AsyncClient, team_space: Space, member: User
) -> None:
    base = f"{SPACES}/{team_space.id}/members"
    for response in (
        await member_client.put(base, json=_entry(member, "admin")),
        await member_client.delete(f"{base}/user/{member.id}"),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "space.not_found"


async def test_members_list_is_paginated(owner: AsyncClient, make_space, make_user) -> None:
    people = [await make_user() for _ in range(5)]
    space = await make_space("team", members=[(p, "viewer") for p in people])
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        page = (await owner.get(f"{SPACES}/{space.id}/members", params=params)).json()
        assert len(page["items"]) <= 2
        seen += [m["member_id"] for m in page["items"]]
        if (cursor := page["next_cursor"]) is None:
            break
    assert sorted(seen) == sorted(str(p.id) for p in people)
