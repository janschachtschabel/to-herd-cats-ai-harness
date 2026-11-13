"""Tickets live (plan M4 task 3): `ticket.created` and `ticket.updated` reach every
stream whose person may see the ticket's space, with ids only, and stop the moment that
person leaves the space (review focus 5). A real server, the real worker handlers."""

from tests.live_helpers import LiveServer, drain
from tests.live_people import Person, make_person, team_channel
from tests.real_db import RealDb


async def test_ticket_changes_reach_the_space_and_stop_with_the_membership(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    outsider = await make_person(real_db, live, "outsider@real.example.com")
    space, _ = await team_channel(owner, member)
    await drain(real_db.database)
    watching, not_in = await member.stream(real_db), await outsider.stream(real_db)
    created = await owner.client.post(
        f"/api/spaces/{space}/tickets", json={"title": "Geheimer Titel"}
    )
    assert created.status_code == 201, created.text
    ticket = created.json()
    await drain(real_db.database)
    event = await watching.until_event("ticket.created")
    assert event.data["ticket_id"] == ticket["id"]
    assert set(event.data) == {"conversation_id", "message_id", "parent_id", "ticket_id"}
    await not_in.expect_nothing()

    removed = await owner.client.delete(f"/api/spaces/{space}/members/user/{member.id}")
    assert removed.status_code == 204
    await drain(real_db.database)
    await watching.settle()
    changed = await owner.client.patch(
        f"/api/tickets/{ticket['number']}", json={"version": 1, "title": "Anders"}
    )
    assert changed.status_code == 200, changed.text
    await drain(real_db.database)
    await watching.expect_nothing()
    await not_in.expect_nothing()
    for stream in (watching, not_in):
        await stream.close()
