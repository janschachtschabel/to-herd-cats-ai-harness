"""Assignments and the derived `ai.use` (plan M5 decision 5, spec 7.2): person before
group before standard, groups in order, guests never, a disabled connection does not
hand on to the next assignment, and people without the right learn nothing."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, require
from app.core.errors import Forbidden
from app.core.outbox import EventOutbox
from app.core.principal import SystemRole
from app.modules.ai.effective import effective_assignment
from app.modules.users.models import User
from tests.factories import MakeUser, login
from tests.factories_groups import MakeGroup
from tests.test_access import actor_of

CONNECTIONS = "/api/ai/connections"
BASE = "/api/ai/assignments"


async def connection(client: AsyncClient, name: str = "Chat", **fields: Any) -> dict[str, Any]:
    body = {
        "name": name,
        "kind": "local",
        "base_url": "http://127.0.0.1:1/v1",
        "models": ["m1", "m2"],
        **fields,
    }
    response = await client.post(CONNECTIONS, json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def set_default(client: AsyncClient, conn: dict[str, Any] | None, model: str = "m1") -> None:
    version = (await client.get(BASE)).json()["version"]
    target = {"connection_id": conn["id"], "model": model} if conn else None
    response = await client.put(f"{BASE}/default", json={"target": target, "version": version})
    assert response.status_code == 200, response.text


async def set_groups(client: AsyncClient, items: list[tuple[Any, dict[str, Any], str]]) -> None:
    version = (await client.get(BASE)).json()["version"]
    body = [{"group_id": str(g), "connection_id": c["id"], "model": m} for g, c, m in items]
    response = await client.put(f"{BASE}/groups", json={"items": body, "version": version})
    assert response.status_code == 200, response.text


async def set_user(
    client: AsyncClient, user: User, conn: dict[str, Any] | None, model: str = "m1"
) -> dict[str, Any]:
    current = (await client.get(f"{BASE}/users")).json()["items"]
    version = next((u["version"] for u in current if u["user_id"] == str(user.id)), None)
    body: dict[str, Any] = {"version": version}
    body.update(
        {"target": {"connection_id": conn["id"], "model": model}} if conn else {"no_ai": True}
    )
    response = await client.put(f"{BASE}/users/{user.id}", json=body)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


async def me(client: AsyncClient) -> tuple[bool, str | None]:
    body = (await client.get("/api/auth/me")).json()
    return "ai.use" in body["permissions"], body["ai_model"]


async def test_nobody_has_ai_until_an_admin_assigns_it(
    owner: AsyncClient, member_client: AsyncClient, guest_client: AsyncClient
) -> None:
    for client in (owner, member_client, guest_client):
        assert await me(client) == (False, None)
    chat = await connection(owner)
    await set_default(owner, chat)
    assert await me(owner) == (True, "m1")
    assert await me(member_client) == (True, "m1")
    assert await me(guest_client) == (False, None)  # guests never
    await set_default(owner, None)
    assert await me(member_client) == (False, None)


async def test_person_before_group_before_standard(
    owner: AsyncClient, member_client: AsyncClient, member: User, make_group: MakeGroup
) -> None:
    chat = await connection(owner)
    other = await connection(owner, "Andere", models=["x1"])
    redaktion = await make_group("Redaktion", members=[member])
    await set_default(owner, chat, "m1")
    await set_groups(owner, [(redaktion.id, chat, "m2")])
    assert await me(member_client) == (True, "m2")
    await set_user(owner, member, other, "x1")
    assert await me(member_client) == (True, "x1")
    await set_user(owner, member, None)  # expressly no AI
    assert await me(member_client) == (False, None)
    version = (await owner.get(f"{BASE}/users")).json()["items"][0]["version"]
    removed = await owner.delete(f"{BASE}/users/{member.id}", params={"version": version})
    assert removed.status_code == 204
    assert await me(member_client) == (True, "m2")


async def test_the_first_matching_group_wins(
    owner: AsyncClient, member_client: AsyncClient, member: User, make_group: MakeGroup
) -> None:
    chat = await connection(owner)
    first = await make_group("A", members=[member])
    second = await make_group("B", members=[member])
    elsewhere = await make_group("C")
    await set_groups(
        owner, [(elsewhere.id, chat, "m1"), (second.id, chat, "m2"), (first.id, chat, "m1")]
    )
    assert await me(member_client) == (True, "m2")
    await set_groups(owner, [(first.id, chat, "m1"), (second.id, chat, "m2")])
    assert await me(member_client) == (True, "m1")
    page = (await owner.get(f"{BASE}/groups", params={"limit": 1})).json()
    assert [g["group_name"] for g in page["items"]] == ["A"] and page["next_cursor"]
    rest = (await owner.get(f"{BASE}/groups", params={"cursor": page["next_cursor"]})).json()
    assert [(g["group_name"], g["position"]) for g in rest["items"]] == [("B", 1)]


async def test_a_disabled_connection_does_not_hand_on_to_the_next(
    owner: AsyncClient, member_client: AsyncClient, member: User
) -> None:
    chat = await connection(owner)
    own = await connection(owner, "Eigene")
    await set_default(owner, chat)
    await set_user(owner, member, own)
    disabled = await owner.patch(
        f"{CONNECTIONS}/{own['id']}", json={"enabled": False, "version": own["version"]}
    )
    assert await me(member_client) == (False, None)  # not the standard instead
    patch = {"enabled": True, "purpose": "embedding", "version": disabled.json()["version"]}
    embedding = await owner.patch(f"{CONNECTIONS}/{own['id']}", json=patch)
    assert await me(member_client) == (False, None)
    patch = {"purpose": "both", "models": ["m2"], "version": embedding.json()["version"]}
    await owner.patch(f"{CONNECTIONS}/{own['id']}", json=patch)
    assert await me(member_client) == (False, None)  # its model m1 is gone


async def test_deactivated_people_and_the_derived_check(
    owner: AsyncClient, session: AsyncSession, member: User
) -> None:
    await set_default(owner, await connection(owner))
    actor = await actor_of(session, member)
    await require(session, actor, Action.AI_USE)
    member.is_active = False
    await session.flush()
    with pytest.raises(Forbidden):
        await require(session, actor, Action.AI_USE)


async def test_resolution_is_one_query(
    owner: AsyncClient, session: AsyncSession, member: User, make_group: MakeGroup
) -> None:
    chat = await connection(owner)
    await make_group("A", members=[member])
    await set_default(owner, chat)
    statements: list[str] = []
    sync_engine = (await session.connection()).sync_engine

    def count(*args: Any) -> None:
        statements.append(args[2])

    event.listen(sync_engine, "before_cursor_execute", count)
    try:
        effective = await effective_assignment(session, member.org_id, member.id)
    finally:
        event.remove(sync_engine, "before_cursor_execute", count)
    assert effective is not None and effective.source == "default"
    assert len(statements) == 1


async def test_non_admins_learn_only_their_model(
    owner: AsyncClient, member_client: AsyncClient
) -> None:
    chat = await connection(owner, "Geheimer Anbieter", base_url="http://10.9.8.7:8000/v1")
    await set_default(owner, chat)
    body = (await member_client.get("/api/auth/me")).text
    assert "m1" in body
    for leak in (chat["id"], "Geheimer Anbieter", "10.9.8.7", "127.0.0.1", '"local"'):
        assert leak not in body
    for path in (BASE, f"{BASE}/groups", f"{BASE}/users", CONNECTIONS):
        response = await member_client.get(path)
        assert response.status_code == 404 and response.json()["error"]["code"] == "ai.not_found"


async def test_targets_are_checked(
    owner: AsyncClient, guest: User, member: User, make_group: MakeGroup
) -> None:
    chat = await connection(owner)
    embedding = await connection(owner, "Emb", purpose="embedding")
    group = await make_group("A")
    cases = [
        (
            {"connection_id": "0190f0f0-0000-7000-8000-000000000000", "model": "m1"},
            "ai.connection_not_found",
        ),
        ({"connection_id": embedding["id"], "model": "m1"}, "ai.connection_not_chat"),
        ({"connection_id": chat["id"], "model": "nope"}, "ai.model_unknown"),
    ]
    for target, code in cases:
        response = await owner.put(f"{BASE}/default", json={"target": target, "version": 1})
        assert response.json()["error"]["code"] == code, target
        response = await owner.put(
            f"{BASE}/users/{member.id}", json={"target": target, "version": None}
        )
        assert response.json()["error"]["code"] == code, target
    good = {"connection_id": chat["id"], "model": "m1"}
    guest_put = await owner.put(f"{BASE}/users/{guest.id}", json={"target": good, "version": None})
    assert guest_put.json()["error"]["code"] == "ai.guest_not_assignable"
    no_ai = await owner.put(f"{BASE}/users/{guest.id}", json={"no_ai": True, "version": None})
    assert no_ai.status_code == 200
    item = {"group_id": str(group.id), **good}
    twice = await owner.put(f"{BASE}/groups", json={"items": [item, item], "version": 1})
    assert twice.json()["error"]["code"] == "ai.group_twice"
    unknown = {**item, "group_id": str(member.id)}
    missing = await owner.put(f"{BASE}/groups", json={"items": [unknown], "version": 1})
    assert missing.json()["error"]["code"] == "ai.group_not_found"
    too_many = await owner.put(f"{BASE}/groups", json={"items": [item] * 101, "version": 1})
    assert too_many.status_code == 422
    both = {"no_ai": True, "target": good, "version": None}
    assert (await owner.put(f"{BASE}/users/{member.id}", json=both)).status_code == 422
    stranger = "0190f0f0-0000-7000-8000-000000000000"
    nobody = await owner.put(f"{BASE}/users/{stranger}", json={"no_ai": True, "version": None})
    assert nobody.status_code == 404


async def test_writes_name_the_version_they_read(owner: AsyncClient, member: User) -> None:
    chat = await connection(owner)
    target = {"connection_id": chat["id"], "model": "m1"}
    assert (await owner.put(f"{BASE}/default", json={"target": target, "version": 1})).json()[
        "version"
    ] == 2
    stale = await owner.put(f"{BASE}/default", json={"target": None, "version": 1})
    assert stale.status_code == 409 and stale.json()["error"]["details"] == {"current_version": 2}
    assert (await owner.put(f"{BASE}/groups", json={"items": [], "version": 1})).status_code == 409
    made = await owner.put(f"{BASE}/users/{member.id}", json={"no_ai": True, "version": None})
    assert made.json()["version"] == 1
    again = await owner.put(f"{BASE}/users/{member.id}", json={"no_ai": True, "version": None})
    assert again.status_code == 409
    old = await owner.delete(f"{BASE}/users/{member.id}", params={"version": 7})
    assert old.status_code == 409


async def test_a_connection_in_use_cannot_be_deleted(
    owner: AsyncClient, member: User, make_group: MakeGroup
) -> None:
    group = await make_group("A")
    for use in ("default", "group", "user"):
        chat = await connection(owner, f"Chat {use}")
        if use == "default":
            await set_default(owner, chat)
        elif use == "group":
            await set_groups(owner, [(group.id, chat, "m1")])
        else:
            await set_user(owner, member, chat)
        refused = await owner.delete(f"{CONNECTIONS}/{chat['id']}", params={"version": 1})
        assert refused.status_code == 409, use
        assert refused.json()["error"]["code"] == "ai.connection_in_use"
        if use == "default":
            await set_default(owner, None)
        elif use == "group":
            await set_groups(owner, [])
        else:
            await set_user(owner, member, None)
        assert (
            await owner.delete(f"{CONNECTIONS}/{chat['id']}", params={"version": 1})
        ).status_code == 204


async def test_a_deleted_group_takes_its_assignment_along(
    owner: AsyncClient, member_client: AsyncClient, member: User, make_group: MakeGroup
) -> None:
    chat = await connection(owner)
    group = await make_group("A", members=[member])
    await set_groups(owner, [(group.id, chat, "m1")])
    assert await me(member_client) == (True, "m1")
    assert (await owner.delete(f"/api/admin/groups/{group.id}")).status_code == 204
    assert (await owner.get(f"{BASE}/groups")).json()["items"] == []
    assert await me(member_client) == (False, None)


async def test_a_person_is_told_when_their_assignment_changes(
    owner: AsyncClient, session: AsyncSession, member: User
) -> None:
    await set_user(owner, member, None)
    events = (
        await session.scalars(select(EventOutbox).where(EventOutbox.subject_id == member.id))
    ).all()
    assert [e.type for e in events] == ["access.changed"]


async def test_assignments_are_audited_without_secrets(
    owner: AsyncClient, make_user: MakeUser, make_client: Any
) -> None:
    admin = await make_user(SystemRole.ADMIN)
    admin_client = await make_client(csrf=True)
    await login(admin_client, admin.email)
    chat = await connection(admin_client)
    await set_default(admin_client, chat)
    audit = (await owner.get("/api/admin/audit")).json()["items"]
    assert any(entry["action"] == "ai_assignment.default_set" for entry in audit)
