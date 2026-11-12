from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, actor_for, can
from app.core.principal import Principal, SystemRole
from app.modules.auth.context import AuthContext
from app.modules.groups.models import Group, GroupMember
from app.modules.groups.repository import GroupRepository
from app.modules.orgs.models import Organization
from app.modules.users.models import User
from tests.factories import login

GROUPS = "/api/admin/groups"


def _member(user: User) -> dict[str, str]:
    return {"member_type": "user", "member_id": str(user.id)}


async def test_admin_creates_group_and_adds_member(owner: AsyncClient, member: User) -> None:
    created = await owner.post(GROUPS, json={"name": "Redaktion", "description": "Texte"})
    assert created.status_code == 201, created.text
    group = created.json()
    assert (group["name"], group["description"], group["version"]) == ("Redaktion", "Texte", 1)

    added = await owner.post(f"{GROUPS}/{group['id']}/members", json=_member(member))
    assert added.status_code == 204
    members = (await owner.get(f"{GROUPS}/{group['id']}/members")).json()
    assert members["items"] == [{**_member(member), "name": "Max Member"}]
    assert (await owner.get(f"{GROUPS}/{group['id']}")).json() == group
    assert [g["id"] for g in (await owner.get(GROUPS)).json()["items"]] == [group["id"]]


async def test_member_cannot_create_group(member_client: AsyncClient) -> None:
    r = await member_client.post(GROUPS, json={"name": "x"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "auth.permission_denied"


async def test_member_and_guest_cannot_use_any_group_route(
    member_client: AsyncClient, guest_client: AsyncClient, group_with_member: Group, member: User
) -> None:
    base = f"{GROUPS}/{group_with_member.id}"
    for client in (member_client, guest_client):
        for response in (
            await client.get(GROUPS),
            await client.get(base),
            await client.patch(base, json={"name": "y", "version": 1}),
            await client.delete(base),
            await client.get(f"{base}/members"),
            await client.post(f"{base}/members", json=_member(member)),
            await client.delete(f"{base}/members/user/{member.id}"),
        ):
            assert response.status_code == 403, response.request.url


async def test_an_admin_manages_groups(make_user, make_client) -> None:
    admin = await make_user(SystemRole.ADMIN)
    client = await make_client(csrf=True)
    await login(client, admin.email)
    assert (await client.post(GROUPS, json={"name": "Team"})).status_code == 201


async def test_group_ids_for_user(
    session: AsyncSession, group_with_member: Group, member: User, owner_user: User
) -> None:
    groups = GroupRepository(session)
    assert await groups.group_ids_for(Principal.user(member.id)) == {group_with_member.id}
    assert await groups.group_ids_for(Principal.user(owner_user.id)) == frozenset()


async def test_actor_knows_its_groups(
    session: AsyncSession, group_with_member: Group, member: User
) -> None:
    actor = await actor_for(session, AuthContext(user=member))
    assert actor.group_ids == {group_with_member.id}
    assert actor.principal == Principal.user(member.id) and actor.org_id == member.org_id
    assert actor.system_role is SystemRole.MEMBER and not actor.is_admin
    assert not await can(session, actor, Action.GROUP_MANAGE)


async def test_deleting_group_removes_memberships(
    owner: AsyncClient, group_with_member: Group, session: AsyncSession
) -> None:
    assert (await owner.delete(f"{GROUPS}/{group_with_member.id}")).status_code == 204
    rows = select(func.count()).select_from(GroupMember)
    assert await session.scalar(rows) == 0
    r = await owner.get(f"{GROUPS}/{group_with_member.id}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "groups.not_found"
    assert (await owner.delete(f"{GROUPS}/{group_with_member.id}")).status_code == 404


async def test_update_checks_version_and_changes_fields(owner: AsyncClient, group: Group) -> None:
    base = f"{GROUPS}/{group.id}"
    r = await owner.patch(base, json={"name": "Lektorat", "description": "neu", "version": 1})
    assert r.status_code == 200, r.text
    assert (r.json()["name"], r.json()["description"], r.json()["version"]) == (
        "Lektorat",
        "neu",
        2,
    )
    stale = await owner.patch(base, json={"name": "X", "version": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "groups.version_conflict"
    # Fields left out stay; an explicit null clears the description.
    r = await owner.patch(base, json={"description": None, "version": 2})
    assert (r.json()["name"], r.json()["description"]) == ("Lektorat", None)
    assert (await owner.patch(base, json={"name": "X"})).status_code == 422
    assert (await owner.patch(base, json={"name": None, "version": 3})).status_code == 422


async def test_names_are_unique(owner: AsyncClient, group: Group, make_group) -> None:
    r = await owner.post(GROUPS, json={"name": group.name})
    assert r.status_code == 409 and r.json()["error"]["code"] == "groups.name_taken"
    other = await make_group("Andere")
    r = await owner.patch(f"{GROUPS}/{other.id}", json={"name": group.name, "version": 1})
    assert r.status_code == 409 and r.json()["error"]["code"] == "groups.name_taken"
    # Renaming to its own name is no conflict.
    r = await owner.patch(f"{GROUPS}/{group.id}", json={"name": group.name, "version": 1})
    assert r.status_code == 200


async def test_members_are_people_of_the_organisation(
    owner: AsyncClient, group: Group, member: User, make_user, session: AsyncSession
) -> None:
    elsewhere = Organization(name="Elsewhere", slug="elsewhere")
    session.add(elsewhere)
    await session.flush()
    stranger = await make_user(organization=elsewhere)
    base = f"{GROUPS}/{group.id}/members"
    r = await owner.post(base, json=_member(stranger))
    assert r.status_code == 404 and r.json()["error"]["code"] == "users.not_found"
    agent = {"member_type": "agent", "member_id": str(member.id)}
    assert (await owner.post(base, json=agent)).status_code == 422
    # Adding twice keeps one membership.
    for _ in range(2):
        assert (await owner.post(base, json=_member(member))).status_code == 204
    assert len((await owner.get(base)).json()["items"]) == 1


async def test_remove_member(owner: AsyncClient, group_with_member: Group, member: User) -> None:
    base = f"{GROUPS}/{group_with_member.id}/members"
    assert (await owner.delete(f"{base}/user/{member.id}")).status_code == 204
    assert (await owner.get(base)).json()["items"] == []
    r = await owner.delete(f"{base}/user/{member.id}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "groups.member_not_found"


async def test_lists_are_paginated(owner: AsyncClient, make_group, make_user) -> None:
    people = [await make_user() for _ in range(3)]
    groups = [await make_group(members=people) for _ in range(3)]
    for url, expected in (
        (GROUPS, {str(g.id) for g in groups}),
        (f"{GROUPS}/{groups[0].id}/members", {str(p.id) for p in people}),
    ):
        seen: list[str] = []
        cursor = None
        while True:
            params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
            page = (await owner.get(url, params=params)).json()
            assert len(page["items"]) <= 2
            seen += [x.get("id") or x["member_id"] for x in page["items"]]
            if (cursor := page["next_cursor"]) is None:
                break
        assert len(seen) == len(expected) and set(seen) == expected
        assert (await owner.get(url, params={"limit": 101})).status_code == 422


async def test_other_organisations_groups_are_invisible(
    owner: AsyncClient, session: AsyncSession
) -> None:
    elsewhere = Organization(name="Elsewhere", slug="elsewhere")
    session.add(elsewhere)
    await session.flush()
    foreign = await GroupRepository(session).add(Group(org_id=elsewhere.id, name="Fremd"))
    assert (await owner.get(GROUPS)).json()["items"] == []
    for response in (
        await owner.get(f"{GROUPS}/{foreign.id}"),
        await owner.patch(f"{GROUPS}/{foreign.id}", json={"name": "X", "version": 1}),
        await owner.delete(f"{GROUPS}/{foreign.id}"),
        await owner.get(f"{GROUPS}/{foreign.id}/members"),
    ):
        assert response.status_code == 404
    # The same name may exist in another organisation.
    assert (await owner.post(GROUPS, json={"name": "Fremd"})).status_code == 201


async def test_create_validates_input(owner: AsyncClient) -> None:
    for bad in ({"name": ""}, {"name": "x" * 121}, {"name": "x", "description": "d" * 501}):
        assert (await owner.post(GROUPS, json=bad)).status_code == 422
