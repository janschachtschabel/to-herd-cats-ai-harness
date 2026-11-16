"""What clients need to decide what to show: the caller's system-wide rights
(`/auth/me` `permissions`), their effective role per space (`my_role`), and display
names next to member and audit ids."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import system_permissions
from app.core.principal import SystemRole
from app.modules.groups.models import Group
from app.modules.users.models import User
from tests.factories import login
from tests.factories_spaces import personal_space_of
from tests.test_access import actor_of

SPACES = "/api/spaces"
ADMIN_SYSTEM = [
    "agent.manage",
    "ai.manage",
    "audit.read",
    "directory.read",
    "dm.inspect",
    "group.manage",
    "page.purge",
    "skill.manage",
    "space.create",
    "tag.manage",
    "user.manage",
]
OWNER_SYSTEM = sorted([*ADMIN_SYSTEM, "backup.manage"])  # owners only (plan M9 decision 10)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (SystemRole.OWNER, OWNER_SYSTEM),
        (SystemRole.ADMIN, ADMIN_SYSTEM),
        (SystemRole.MEMBER, ["directory.read", "space.create"]),
        (SystemRole.GUEST, []),
    ],
)
async def test_me_lists_system_permissions(
    role: SystemRole, expected: list[str], make_user, make_client
) -> None:
    user = await make_user(role)
    client = await make_client(csrf=True)
    assert (await login(client, user.email))["permissions"] == expected
    assert (await client.get("/api/auth/me")).json()["permissions"] == expected


async def test_system_permissions_are_read_live(session: AsyncSession, member: User) -> None:
    actor = await actor_of(session, member)
    assert [a.value for a in await system_permissions(session, actor)] == [
        "directory.read",
        "space.create",
    ]
    member.system_role = SystemRole.ADMIN
    await session.flush()
    assert [a.value for a in await system_permissions(session, actor)] == ADMIN_SYSTEM
    member.is_active = False
    await session.flush()
    assert await system_permissions(session, actor) == []


async def test_my_role_in_list_and_detail(
    member_client: AsyncClient,
    owner: AsyncClient,
    member: User,
    make_space,
    make_group,
    session: AsyncSession,
) -> None:
    team = await make_space("team", "Direkt", members=[(member, "editor")])
    redaktion: Group = await make_group("Redaktion", members=[member])
    group_team = await make_space("team", "Über Gruppe", members=[(redaktion, "moderator")])
    general = await make_space("open", "Handbuch")
    foreign = await make_space("team", "Fremd")
    own = await personal_space_of(session, member)
    expected = {
        str(team.id): "editor",
        str(group_team.id): "moderator",
        str(general.id): "viewer",
        str(own.id): "admin",
    }
    items = (await member_client.get(SPACES)).json()["items"]
    assert {s["id"]: s["my_role"] for s in items} == expected
    for space_id, role in expected.items():
        assert (await member_client.get(f"{SPACES}/{space_id}")).json()["my_role"] == role

    # System admins hold every right in every space: they are shown as its admin.
    owner_items = (await owner.get(SPACES)).json()["items"]
    assert str(foreign.id) in {s["id"] for s in owner_items}
    assert {s["my_role"] for s in owner_items} == {"admin"}


async def test_guest_role_in_open_space_comes_from_membership(
    guest_client: AsyncClient, guest: User, make_space
) -> None:
    space = await make_space("open", members=[(guest, "viewer")])
    body = (await guest_client.get(f"{SPACES}/{space.id}")).json()
    assert body["my_role"] == "viewer"


async def test_my_role_after_create_and_update(member_client: AsyncClient) -> None:
    created = (await member_client.post(SPACES, json={"kind": "team", "name": "Neu"})).json()
    assert created["my_role"] == "admin"
    updated = await member_client.patch(
        f"{SPACES}/{created['id']}", json={"name": "Neuer", "version": created["version"]}
    )
    assert updated.json()["my_role"] == "admin"


async def test_space_members_carry_names(
    owner: AsyncClient, member: User, make_space, make_group
) -> None:
    group = await make_group("Redaktion")
    space = await make_space("team", members=[(member, "viewer")])
    put = await owner.put(
        f"{SPACES}/{space.id}/members",
        json={"member_type": "group", "member_id": str(group.id), "role": "editor"},
    )
    assert put.json()["name"] == "Redaktion"
    items = (await owner.get(f"{SPACES}/{space.id}/members")).json()["items"]
    assert sorted((m["member_type"], m["name"]) for m in items) == [
        ("group", "Redaktion"),
        ("user", "Max Member"),
    ]


async def test_group_members_carry_names(owner: AsyncClient, member: User, make_group) -> None:
    group = await make_group(members=[member])
    items = (await owner.get(f"/api/admin/groups/{group.id}/members")).json()["items"]
    assert items == [{"member_type": "user", "member_id": str(member.id), "name": "Max Member"}]


async def test_audit_entries_carry_the_actor_name(owner: AsyncClient) -> None:
    await owner.post(SPACES, json={"kind": "team", "name": "Protokolliert"})
    entry = (await owner.get("/api/admin/audit")).json()["items"][0]
    assert (entry["action"], entry["actor_name"]) == ("space.created", "Olga Owner")
