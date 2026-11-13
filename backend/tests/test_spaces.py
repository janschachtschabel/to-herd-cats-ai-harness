import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.config import Settings
from app.modules.orgs.models import Organization
from app.modules.orgs.service import ensure_bootstrap
from app.modules.spaces.models import Space, SpaceKind, SpaceMember
from app.modules.spaces.service import SpaceService
from app.modules.users.models import User
from tests.factories import login
from tests.factories_spaces import personal_space_of

SPACES = "/api/spaces"


async def _ids(client: AsyncClient) -> list[str]:
    return [s["id"] for s in (await client.get(SPACES)).json()["items"]]


async def test_new_user_gets_personal_space(owner: AsyncClient, make_client) -> None:
    created = await owner.post(
        "/api/admin/users",
        json={"email": "lea@example.com", "name": "Lea Löwe", "password": "lea-password-1"},
    )
    assert created.status_code == 201
    lea = await make_client(csrf=True)
    await login(lea, "lea@example.com", "lea-password-1")
    spaces = (await lea.get(SPACES)).json()["items"]
    assert [s["kind"] for s in spaces] == ["personal"]
    space = spaces[0]
    assert space["name"] == "Lea Löwe"
    assert space["owner_user_id"] == created.json()["id"]
    members = (await lea.get(f"{SPACES}/{space['id']}/members")).json()["items"]
    assert members == [
        {
            "member_type": "user",
            "member_id": space["owner_user_id"],
            "role": "admin",
            "name": "Lea Löwe",
        }
    ]


async def test_cannot_create_personal_via_api(member_client: AsyncClient) -> None:
    r = await member_client.post(SPACES, json={"kind": "personal", "name": "x"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "spaces.kind_not_allowed"


async def test_guest_cannot_create_space(guest_client: AsyncClient) -> None:
    for kind in ("team", "open"):
        r = await guest_client.post(SPACES, json={"kind": kind, "name": "x"})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "auth.permission_denied"


@pytest.mark.parametrize("kind", ["open", "team"])
async def test_member_creates_space_and_administers_it(
    kind: str, member_client: AsyncClient, member: User
) -> None:
    r = await member_client.post(
        SPACES, json={"kind": kind, "name": "Projekt Übersicht", "description": "d", "icon": "📁"}
    )
    assert r.status_code == 201, r.text
    space = r.json()
    assert (space["kind"], space["name"], space["version"]) == (kind, "Projekt Übersicht", 1)
    assert (space["description"], space["icon"], space["owner_user_id"]) == ("d", "📁", None)
    members = (await member_client.get(f"{SPACES}/{space['id']}/members")).json()["items"]
    assert members == [
        {"member_type": "user", "member_id": str(member.id), "role": "admin", "name": member.name}
    ]
    assert (await member_client.get(f"{SPACES}/{space['id']}")).json() == space


async def test_names_need_not_be_unique(owner: AsyncClient, make_user) -> None:
    ids = {
        (await owner.post(SPACES, json={"kind": "team", "name": "Projekt X"})).json()["id"]
        for _ in range(3)
    }
    assert len(ids) == 3
    first = await make_user(name="Kim")
    second = await make_user(name="Kim")
    names = {s["owner_user_id"]: s["name"] for s in (await owner.get(SPACES)).json()["items"]}
    assert (names[str(first.id)], names[str(second.id)]) == ("Kim", "Kim")


@pytest.mark.parametrize("kind", ["team", "personal"])
async def test_non_member_sees_neither_content_nor_existence(
    kind: str, member_client: AsyncClient, make_space, make_user, session: AsyncSession
) -> None:
    other = await make_user()
    space = (
        await personal_space_of(session, other) if kind == "personal" else await make_space(kind)
    )
    for response in (
        await member_client.get(f"{SPACES}/{space.id}"),
        await member_client.get(f"{SPACES}/{uuid7()}"),
        await member_client.patch(f"{SPACES}/{space.id}", json={"name": "x", "version": 1}),
        await member_client.get(f"{SPACES}/{space.id}/members"),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "space.not_found"
    assert str(space.id) not in await _ids(member_client)


async def test_open_space_visible_to_member_not_guest(
    member_client: AsyncClient, guest_client: AsyncClient, open_space: Space
) -> None:
    assert (await member_client.get(f"{SPACES}/{open_space.id}")).status_code == 200
    assert str(open_space.id) in await _ids(member_client)
    assert (await guest_client.get(f"{SPACES}/{open_space.id}")).status_code == 404
    assert str(open_space.id) not in await _ids(guest_client)
    # Reading is not managing.
    r = await member_client.patch(f"{SPACES}/{open_space.id}", json={"name": "x", "version": 1})
    assert r.status_code == 403 and r.json()["error"]["code"] == "auth.permission_denied"


async def test_admin_sees_every_space(
    owner: AsyncClient, team_space: Space, open_space: Space, member: User, session
) -> None:
    personal = await personal_space_of(session, member)
    ids = await _ids(owner)
    for space in (team_space, open_space, personal):
        assert str(space.id) in ids
        assert (await owner.get(f"{SPACES}/{space.id}")).status_code == 200


async def test_other_organisations_spaces_are_invisible(
    owner: AsyncClient, session: AsyncSession
) -> None:
    elsewhere = Organization(name="Elsewhere")
    session.add(elsewhere)
    await session.flush()
    foreign = Space(org_id=elsewhere.id, kind=SpaceKind.OPEN, name="Fremd")
    session.add(foreign)
    await session.flush()
    assert (await owner.get(f"{SPACES}/{foreign.id}")).status_code == 404
    assert str(foreign.id) not in await _ids(owner)


async def test_update_checks_version_and_never_changes_kind(
    member_client: AsyncClient, make_space, member: User
) -> None:
    space = await make_space("team", members=[(member, "admin")])
    base = f"{SPACES}/{space.id}"
    r = await member_client.patch(
        base, json={"name": "Neu", "description": "x", "icon": "🍎", "version": 1}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["name"], body["description"], body["icon"], body["version"]) == (
        "Neu",
        "x",
        "🍎",
        2,
    )
    stale = await member_client.patch(base, json={"name": "Alt", "version": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "spaces.version_conflict"
    r = await member_client.patch(base, json={"description": None, "icon": None, "version": 2})
    assert (r.json()["name"], r.json()["description"], r.json()["icon"]) == ("Neu", None, None)
    for bad in ({"kind": "open", "version": 3}, {"name": None, "version": 3}, {"name": "x"}):
        assert (await member_client.patch(base, json=bad)).status_code == 422


async def test_list_is_paginated(owner: AsyncClient, make_space) -> None:
    for _ in range(4):
        await make_space()
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        page = (await owner.get(SPACES, params=params)).json()
        assert len(page["items"]) <= 2
        seen += [s["id"] for s in page["items"]]
        if (cursor := page["next_cursor"]) is None:
            break
    assert len(seen) == len(set(seen)) == 5  # four team spaces and the owner's own
    assert (await owner.get(SPACES, params={"limit": 101})).status_code == 422


async def test_create_validates_input(member_client: AsyncClient) -> None:
    for bad in (
        {"kind": "team", "name": ""},
        {"kind": "team", "name": "x" * 121},
        {"kind": "secret", "name": "x"},
        {"kind": "team", "name": "x", "icon": "i" * 33},
        {"name": "x"},
    ):
        assert (await member_client.post(SPACES, json=bad)).status_code == 422


BOOT = Settings(bootstrap_admin_email="boss@example.com", bootstrap_admin_password="pw-123456789")


async def test_bootstrap_creates_allgemein_once(session: AsyncSession) -> None:
    await ensure_bootstrap(session, BOOT)
    await ensure_bootstrap(session, BOOT)
    spaces = (await session.scalars(select(Space).order_by(Space.kind))).all()
    assert [(s.kind, s.name) for s in spaces] == [
        ("open", "Allgemein"),
        ("personal", "boss"),
    ]
    boss = (await session.scalars(select(User))).one()
    assert spaces[1].owner_user_id == boss.id


async def test_every_person_has_exactly_one_personal_space(
    session: AsyncSession, make_user
) -> None:
    user = await make_user()
    count = select(func.count()).select_from(Space).where(Space.owner_user_id == user.id)
    assert await session.scalar(count) == 1
    members = select(func.count()).select_from(SpaceMember).where(SpaceMember.member_id == user.id)
    assert await session.scalar(members) == 1
    with pytest.raises(IntegrityError):  # the database refuses a second one
        async with session.begin_nested():
            await SpaceService(session).create_personal(user)


async def test_list_can_leave_out_other_peoples_personal_spaces(
    owner: AsyncClient, owner_user, make_user, make_space
) -> None:
    """What the sidebar asks for: an admin sees everyone's personal space, but the
    filter is applied before paging, so later team spaces are not pushed off page 1."""
    for _ in range(3):
        await make_user()
    team = await make_space()
    everything = (await owner.get(SPACES, params={"limit": 100})).json()["items"]
    assert sum(s["kind"] == "personal" for s in everything) == 4
    seen: list[dict] = []
    cursor = None
    while True:
        params = {"limit": 1, "include_others_personal": "false"}
        params |= {"cursor": cursor} if cursor else {}
        page = (await owner.get(SPACES, params=params)).json()
        seen += page["items"]
        if (cursor := page["next_cursor"]) is None:
            break
    own = [s["id"] for s in everything if s["owner_user_id"] == str(owner_user.id)]
    assert sorted(s["id"] for s in seen) == sorted([str(team.id), *own])
