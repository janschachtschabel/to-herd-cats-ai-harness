"""Live delivery (plan M3 task 7, review focus 1): `GET /api/stream` over the worker's
`publish_live` handler and each API process's LISTEN hub, against a real server and
real commits. Payloads carry ids only; who gets an event is decided from the database
as it is then. Ending streams, limits and resync: `test_live_streams.py`."""

from tests.live_helpers import LiveServer, drain
from tests.live_people import SECRET, Person, make_person, say, stranger, team_channel
from tests.real_db import RealDb


async def test_member_receives_message_event_with_ids_only(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    _, channel = await team_channel(owner, member)
    await drain(real_db.database)
    stream = await member.stream(real_db)
    response = stream.response
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"

    message = await say(owner, channel)
    await drain(real_db.database)
    event = await stream.next()
    assert event.name == "message.created"
    assert event.data == {
        "conversation_id": channel,
        "message_id": message["id"],
        "parent_id": None,
    }
    reply = await owner.client.post(
        f"/api/conversations/{channel}/messages",
        json={"body_md": SECRET, "parent_id": message["id"]},
    )
    await drain(real_db.database)
    event = await stream.next()
    assert event.data["parent_id"] == message["id"]
    assert event.data["message_id"] == reply.json()["id"]
    await stream.expect_nothing()
    assert not any(SECRET in line for line in stream.raw)
    await stream.close()


async def test_non_member_and_other_org_receive_nothing(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    _, channel = await team_channel(owner)  # the member is not in it
    other = await stranger(real_db, live)
    await drain(real_db.database)
    streams = [await member.stream(real_db), await other.stream(real_db)]
    await say(owner, channel)
    await drain(real_db.database)
    for stream in streams:
        await stream.expect_nothing()
        await stream.close()


async def test_revoked_member_stops_receiving_without_reconnect(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    space, channel = await team_channel(owner, member)
    await drain(real_db.database)
    stream = await member.stream(real_db)
    await say(owner, channel, "vorher")
    await drain(real_db.database)
    assert (await stream.next()).name == "message.created"

    removed = await owner.client.delete(f"/api/spaces/{space}/members/user/{member.id}")
    assert removed.status_code == 204, removed.text
    await say(owner, channel)
    await drain(real_db.database)
    assert (await stream.next()).name == "access.changed"  # (test_live_access.py)
    await stream.expect_nothing()
    assert not stream.ended.is_set()  # the same connection, still open
    await stream.close()


async def test_dm_event_reaches_only_participants_not_admins(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    carol = await make_person(real_db, live, "carol@real.example.com")
    dm = (await member.client.post("/api/dms", json={"user_ids": [carol.id]})).json()
    inspection = await owner.client.post(
        "/api/admin/dm-inspect",
        json={"conversation_id": dm["id"], "reason": "a reason that is long enough"},
    )
    assert inspection.status_code == 201, inspection.text  # an inspection opens no stream
    await drain(real_db.database)
    watching = [
        await owner.stream(real_db),
        await member.stream(real_db),
        await carol.stream(real_db),
    ]
    message = await say(member, dm["id"])
    await drain(real_db.database)
    for stream in watching[1:]:
        event = await stream.until_event("message.created")
        assert event.data["message_id"] == message["id"]
    await watching[0].expect_nothing()
    for stream in watching:
        await stream.close()


async def test_events_for_one_person_reach_only_that_person(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    """`notification.created` and `conversation.read` name their person (`u`)."""
    owner, member = pair
    viewer = await make_person(real_db, live, "viewer@real.example.com")
    _, channel = await team_channel(owner, member, viewer)
    await drain(real_db.database)
    streams = [await member.stream(real_db), await viewer.stream(real_db)]
    sent = await owner.client.post(
        f"/api/conversations/{channel}/messages",
        json={"body_md": "@member", "mentions": [member.id]},
    )
    await drain(real_db.database)
    message_id = sent.json()["id"]
    notified = await streams[0].until_event("notification.created")
    assert notified.data == {
        "conversation_id": channel,
        "message_id": message_id,
        "parent_id": None,
    }
    read = await member.client.post(
        f"/api/conversations/{channel}/read", json={"message_id": message_id}
    )
    assert read.status_code == 204
    await drain(real_db.database)
    assert (await streams[0].until_event("conversation.read")).data["message_id"] == message_id
    await streams[0].expect_nothing()
    assert (await streams[1].next()).name == "message.created"  # the viewer: only the message
    await streams[1].expect_nothing()
    for stream in streams:
        await stream.close()
