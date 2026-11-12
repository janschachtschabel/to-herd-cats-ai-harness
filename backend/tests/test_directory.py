"""The directory: people and groups a space admin can add, for everyone but guests.
Only active people and groups of the caller's organisation; only type, id and name."""

from httpx import AsyncClient

from app.core.principal import SystemRole
from app.modules.orgs.models import Organization
from app.modules.users.models import User

DIRECTORY = "/api/directory"


async def _entries(client: AsyncClient, **params: object) -> list[dict[str, str]]:
    response = await client.get(DIRECTORY, params=params)
    assert response.status_code == 200, response.text
    items: list[dict[str, str]] = response.json()["items"]
    return items


async def test_member_finds_people_and_groups_by_name(
    member_client: AsyncClient, make_user, make_group
) -> None:
    lea = await make_user(name="Lea Lange", email="lea@example.com")
    team = await make_group("Leitung")
    await make_user(name="Otto Other", email="otto@example.com")

    found = await _entries(member_client, q="LE")
    assert {"type": "user", "id": str(lea.id), "name": "Lea Lange"} in found
    assert {"type": "group", "id": str(team.id), "name": "Leitung"} in found
    assert "Otto Other" not in {e["name"] for e in found}


async def test_entries_have_type_id_and_name_only(member_client: AsyncClient, member) -> None:
    response = await member_client.get(DIRECTORY, params={"q": "Max"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "next_cursor"}
    assert body["items"] == [{"type": "user", "id": str(member.id), "name": "Max Member"}]


async def test_email_does_not_match(member_client: AsyncClient, make_user) -> None:
    """Members must not be able to probe whether an email address exists in the org."""
    await make_user(name="Lea Lange", email="l.lange@example.com")
    assert await _entries(member_client, q="l.lange") == []
    assert await _entries(member_client, q="l.lange@example.com") == []
    assert await _entries(member_client, q="example.com") == []
    assert len(await _entries(member_client, q="Lea")) == 1


async def test_wildcards_in_q_are_literal(member_client: AsyncClient, make_user) -> None:
    await make_user(name="Lea Lange")
    assert await _entries(member_client, q="%") == []
    assert await _entries(member_client, q="L_a") == []


async def test_type_filter(member_client: AsyncClient, make_user, make_group) -> None:
    await make_user(name="Redakteurin")
    await make_group("Redaktion")
    assert {e["type"] for e in await _entries(member_client, q="Redak", type="user")} == {"user"}
    assert {e["type"] for e in await _entries(member_client, q="Redak", type="group")} == {"group"}
    assert (await member_client.get(DIRECTORY, params={"type": "agent"})).status_code == 422


async def test_inactive_people_and_other_organisations_are_left_out(
    member_client: AsyncClient, make_user, session
) -> None:
    await make_user(name="Ina Inaktiv", is_active=False)
    other = Organization(name="Other", slug="other")
    session.add(other)
    await session.flush()
    await make_user(name="Fritz Fremd", organization=other)
    names = {e["name"] for e in await _entries(member_client, limit=100)}
    assert "Ina Inaktiv" not in names
    assert "Fritz Fremd" not in names


async def test_sorted_by_name_and_paged(member_client: AsyncClient, make_user, make_group) -> None:
    await make_user(name="Paul B")
    await make_group("paul a")
    await make_user(name="Paul C")
    await make_user(name="Pauline D")
    first = (await member_client.get(DIRECTORY, params={"q": "paul", "limit": 2})).json()
    assert [e["name"] for e in first["items"]] == ["paul a", "Paul B"]
    assert first["next_cursor"]
    params = {"q": "paul", "limit": 2, "cursor": first["next_cursor"]}
    second = (await member_client.get(DIRECTORY, params=params)).json()
    assert [e["name"] for e in second["items"]] == ["Paul C", "Pauline D"]
    assert second["next_cursor"] is None


async def test_same_names_page_without_gaps(member_client: AsyncClient, make_user) -> None:
    made = {str((await make_user(name="Kim Same")).id) for _ in range(3)}
    seen: list[str] = []
    cursor = None
    while True:
        params: dict[str, object] = {"q": "Kim Same", "limit": 1}
        if cursor:
            params["cursor"] = cursor
        body = (await member_client.get(DIRECTORY, params=params)).json()
        seen += [e["id"] for e in body["items"]]
        if not (cursor := body["next_cursor"]):
            break
    assert sorted(seen) == sorted(made)


async def test_bad_input_is_422(member_client: AsyncClient) -> None:
    for params in ({"cursor": "not-a-cursor"}, {"limit": 101}, {"q": "x" * 101}):
        response = await member_client.get(DIRECTORY, params=params)
        assert response.status_code == 422, params


async def test_admins_may_read_the_directory(make_user, make_client) -> None:
    from tests.factories import login

    for role in (SystemRole.ADMIN, SystemRole.OWNER):
        user: User = await make_user(role)
        client = await make_client(csrf=True)
        await login(client, user.email)
        assert (await client.get(DIRECTORY)).status_code == 200


async def test_guests_may_not_read_the_directory(guest_client: AsyncClient) -> None:
    response = await guest_client.get(DIRECTORY)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "auth.permission_denied"


async def test_anonymous_callers_are_refused(client: AsyncClient) -> None:
    assert (await client.get(DIRECTORY)).status_code == 401
