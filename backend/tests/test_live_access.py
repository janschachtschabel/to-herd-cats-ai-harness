"""Live events about access (review M3 N6, N7): a person whose access changes (a space
membership or role, directly or through a group) gets `access.changed` at once, ids
only, so the client drops what it may no longer show; the participants of a DM an
administrator inspects get `dm.inspected` with the conversation's id only."""

from tests.live_helpers import LiveServer, drain
from tests.live_people import Person, make_person, say, team_channel
from tests.real_db import RealDb

NO_IDS = {"conversation_id": None, "message_id": None, "parent_id": None}


async def test_removal_from_a_space_reaches_the_removed_person_at_once(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    bystander = await make_person(real_db, live, "bystander@real.example.com")
    space, channel = await team_channel(owner, member, bystander)
    await drain(real_db.database)
    removed_stream, other = await member.stream(real_db), await bystander.stream(real_db)
    removed = await owner.client.delete(f"/api/spaces/{space}/members/user/{member.id}")
    assert removed.status_code == 204, removed.text
    await drain(real_db.database)
    event = await removed_stream.next()
    assert (event.name, event.data) == ("access.changed", NO_IDS)
    await removed_stream.expect_nothing()
    await other.expect_nothing()  # only the person concerned

    changed = await owner.client.put(  # a role change, too
        f"/api/spaces/{space}/members",
        json={"member_type": "user", "member_id": bystander.id, "role": "editor"},
    )
    assert changed.status_code in (200, 201), changed.text
    await drain(real_db.database)
    assert (await other.next()).name == "access.changed"
    await say(owner, channel)
    await drain(real_db.database)
    assert (await other.next()).name == "message.created"
    await removed_stream.expect_nothing()
    for stream in (removed_stream, other):
        await stream.close()


async def test_a_group_change_reaches_its_members(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    groups = "/api/admin/groups"
    group = (await owner.client.post(groups, json={"name": "Team A"})).json()
    join = {"member_type": "user", "member_id": member.id}
    added = await owner.client.post(f"{groups}/{group['id']}/members", json=join)
    assert added.status_code == 204, added.text
    space, _ = await team_channel(owner)
    granted = await owner.client.put(
        f"/api/spaces/{space}/members",
        json={"member_type": "group", "member_id": group["id"], "role": "viewer"},
    )
    assert granted.status_code in (200, 201), granted.text
    await drain(real_db.database)
    stream = await member.stream(real_db)
    left = await owner.client.delete(f"{groups}/{group['id']}/members/user/{member.id}")
    assert left.status_code == 204, left.text
    await drain(real_db.database)
    assert (await stream.next()).name == "access.changed"
    await owner.client.post(f"{groups}/{group['id']}/members", json=join)
    await drain(real_db.database)
    assert (await stream.next()).name == "access.changed"
    gone = await owner.client.delete(f"/api/spaces/{space}/members/group/{group['id']}")
    assert gone.status_code == 204, gone.text
    await drain(real_db.database)
    assert (await stream.next()).name == "access.changed"
    await stream.expect_nothing()
    await stream.close()


async def test_the_participants_see_an_inspection_at_once(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    carol = await make_person(real_db, live, "carol@real.example.com")
    outsider = await make_person(real_db, live, "outsider@real.example.com")
    dm = (await member.client.post("/api/dms", json={"user_ids": [carol.id]})).json()
    await drain(real_db.database)
    streams = [await s.stream(real_db) for s in (member, carol, owner, outsider)]
    inspection = await owner.client.post(
        "/api/admin/dm-inspect",
        json={"conversation_id": dm["id"], "reason": "a reason that is long enough"},
    )
    assert inspection.status_code == 201, inspection.text
    await drain(real_db.database)
    for stream in streams[:2]:
        event = await stream.next()
        assert (event.name, event.data) == ("dm.inspected", {**NO_IDS, "conversation_id": dm["id"]})
    for stream in streams[2:]:  # the inspecting admin is no participant
        await stream.expect_nothing()
    for stream in streams:
        await stream.close()
