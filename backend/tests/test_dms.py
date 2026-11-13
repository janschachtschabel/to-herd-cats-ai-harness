"""Direct messages (spec 6.1, 5.5): 2 to 9 people, the same group always meets in the
same conversation, only participants see it. Admins have no right in a DM of others
(only the audited inspection, tests/test_dm_inspect.py)."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.modules.messaging.models import Conversation, ConversationParticipant
from app.modules.orgs.models import Organization
from tests.factories_dms import DMS, People, dm_of, open_dm
from tests.factories_messaging import post, send


def _conversation(conversation_id: object) -> str:
    return f"/api/conversations/{conversation_id}"


async def test_the_same_group_always_gets_the_same_conversation(people: People) -> None:
    first = await open_dm(people.alice, people.id("bob"))
    assert first.status_code == 201, first.text
    dm = first.json()
    assert dm["kind"] == "dm" and dm["space_id"] is None and dm["name"] is None
    assert dm["can_post"] is True and dm["inspections"] == []
    assert dm["created_by"] == {"type": "user", "id": people.id("alice")}
    names = {(p["id"], p["name"], p["is_active"]) for p in dm["participants"]}
    assert names == {(people.id("alice"), "Alice", True), (people.id("bob"), "Bob", True)}
    for client, ids in (
        (people.alice, [people.id("bob")]),
        (people.alice, [people.id("bob"), people.id("alice"), people.id("bob")]),
        (people.bob, [people.id("alice")]),
    ):
        again = await open_dm(client, *ids)
        assert again.status_code == 200, again.text
        assert again.json()["id"] == dm["id"]
    group = await dm_of(people.alice, people.id("bob"), people.id("carol"))
    assert group["id"] != dm["id"]
    assert (await dm_of(people.carol, people.id("bob"), people.id("alice")))["id"] == group["id"]


async def test_participants_read_and_write_and_nobody_else_sees_it(people: People) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    message = await post(people.alice, dm["id"], "Unter uns")
    reply = await post(people.bob, dm["id"], "Klar", parent_id=message["id"])
    listed = (await people.bob.get(f"{_conversation(dm['id'])}/messages")).json()["items"]
    assert [(m["id"], m["reply_count"]) for m in listed] == [(message["id"], 1)]
    for outsider in (people.carol, people.admin, people.gast):
        for method, path, body in (
            ("GET", _conversation(dm["id"]), None),
            ("GET", f"{_conversation(dm['id'])}/messages", None),
            ("POST", f"{_conversation(dm['id'])}/messages", {"body_md": "rein"}),
        ):
            response = await outsider.request(method, path, json=body)
            assert response.status_code == 404, (method, path, response.text)
            assert response.json()["error"]["code"] == "conversation.not_found"
        for method, path, body in (
            ("GET", f"/api/messages/{message['id']}/replies", None),
            ("PATCH", f"/api/messages/{reply['id']}", {"body_md": "x"}),
            ("DELETE", f"/api/messages/{reply['id']}", None),
        ):
            response = await outsider.request(method, path, json=body)
            assert response.status_code == 404, (method, path, response.text)
            assert response.json()["error"]["code"] == "message.not_found"


async def test_a_dm_is_no_channel(people: People) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    for path, body in (
        (_conversation(dm["id"]), {"topic": "x", "version": 1}),
        (f"{_conversation(dm['id'])}/archive", {"version": 1}),
    ):
        method = "PATCH" if body.get("topic") else "POST"
        response = await people.alice.request(method, path, json=body)
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "conversation.not_a_channel"
    message = await post(people.bob, dm["id"], "meins")
    refused = await people.alice.delete(f"/api/messages/{message['id']}")
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "message.not_author"
    assert (await people.bob.delete(f"/api/messages/{message['id']}")).status_code == 204
    channels = (await people.alice.get("/api/channels")).json()["items"]
    assert dm["id"] not in {c["id"] for c in channels}


async def test_guests_cannot_open_but_answer(people: People) -> None:
    refused = await open_dm(people.gast, people.id("alice"))
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "dm.guest_cannot_open"
    dm = await dm_of(people.alice, people.id("gast"))
    assert (await send(people.gast, dm["id"], "Danke")).status_code == 201
    listed = (await people.gast.get(DMS)).json()["items"]
    assert [d["id"] for d in listed] == [dm["id"]]


async def test_who_can_take_part(people: People, make_user, session: AsyncSession) -> None:
    inactive = await make_user(name="Weg", is_active=False)
    elsewhere = Organization(name="Andere")
    session.add(elsewhere)
    await session.flush()
    stranger = await make_user(organization=elsewhere)
    many = [await make_user() for _ in range(9)]
    for ids in (
        [],
        [people.id("alice")],  # oneself only
        [str(uuid.uuid4())],
        [str(inactive.id)],
        [str(stranger.id)],
        [str(u.id) for u in many],  # ten with oneself
    ):
        response = await people.alice.post(DMS, json={"user_ids": ids})
        assert response.status_code == 422, (ids, response.text)
        assert response.json()["error"]["code"] in ("dm.participants_invalid", "validation_failed")
    nine = await open_dm(people.alice, *[u.id for u in many[:8]])
    assert nine.status_code == 201 and len(nine.json()["participants"]) == 9


async def test_own_dms_by_last_activity(people: People) -> None:
    with_bob = await dm_of(people.alice, people.id("bob"))
    with_carol = await dm_of(people.alice, people.id("carol"))
    await dm_of(people.bob, people.id("carol"))  # not Alice's
    listed = (await people.alice.get(DMS)).json()["items"]
    assert [d["id"] for d in listed] == [with_carol["id"], with_bob["id"]]
    assert all(d["last_message_at"] is None for d in listed)
    message = await post(people.bob, with_bob["id"], "Hallo")
    first = (await people.alice.get(DMS, params={"limit": 1})).json()
    assert [d["id"] for d in first["items"]] == [with_bob["id"]]
    assert first["items"][0]["last_message_at"] == message["created_at"]
    assert {p["name"] for p in first["items"][0]["participants"]} == {"Alice", "Bob"}
    rest = (await people.alice.get(DMS, params={"cursor": first["next_cursor"]})).json()
    assert [d["id"] for d in rest["items"]] == [with_carol["id"]]
    assert rest["next_cursor"] is None


async def test_a_deactivated_participant_stays_listed_but_reads_nothing(
    people: People, session: AsyncSession
) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    people.users["bob"].is_active = False
    await session.flush()
    shown = (await people.alice.get(_conversation(dm["id"]))).json()
    bob = next(p for p in shown["participants"] if p["id"] == people.id("bob"))
    assert bob["is_active"] is False
    assert (await send(people.alice, dm["id"], "Noch da?")).status_code == 201
    assert (await people.bob.get(_conversation(dm["id"]))).status_code == 401


async def test_opening_emits_ids_only(people: People, session: AsyncSession) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    await dm_of(people.bob, people.id("alice"))  # known: nothing new
    events = (
        await session.scalars(select(EventOutbox).where(EventOutbox.type == "dm.created"))
    ).all()
    assert [(e.subject_type, str(e.subject_id), e.space_id, e.payload) for e in events] == [
        ("conversation", dm["id"], None, {"conversation_id": dm["id"]})
    ]


async def test_the_database_keeps_dms_apart_from_spaces(
    people: People, session: AsyncSession, team_space
) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    stored = await session.get(Conversation, uuid.UUID(dm["id"]))
    assert stored is not None and stored.dm_key is not None and len(stored.dm_key) == 64
    participants = await session.scalars(
        select(ConversationParticipant.principal_id).where(
            ConversationParticipant.conversation_id == stored.id
        )
    )
    assert set(participants) == {people.users["alice"].id, people.users["bob"].id}
    for statement in (
        "UPDATE conversation SET space_id = :space WHERE id = :id",
        "UPDATE conversation SET dm_key = NULL WHERE id = :id",
        "UPDATE conversation SET name = 'x' WHERE id = :id",
    ):
        nested = await session.begin_nested()
        try:
            await session.execute(text(statement), {"id": stored.id, "space": team_space.id})
        except DBAPIError:
            await nested.rollback()
        else:
            raise AssertionError(statement)
