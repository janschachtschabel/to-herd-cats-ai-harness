"""Sprints live (plan M4b task 1): every change of a sprint reaches, as `sprint.changed`
with the space's and the sprint's id only, every stream whose person may read the
space's tickets, and stops the moment that person leaves the space. A real server,
the real worker handlers."""

from tests.live_helpers import LiveServer, drain
from tests.live_people import Person, make_person, team_channel
from tests.real_db import RealDb


async def test_sprint_changes_reach_the_space_and_stop_with_the_membership(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    outsider = await make_person(real_db, live, "outsider@real.example.com")
    space, _ = await team_channel(owner, member)
    await drain(real_db.database)
    watching, not_in = await member.stream(real_db), await outsider.stream(real_db)
    created = await owner.client.post(
        f"/api/spaces/{space}/sprints",
        json={"name": "Geheimer Sprint", "starts_on": "2026-11-16", "ends_on": "2026-11-27"},
    )
    assert created.status_code == 201, created.text
    sprint = created.json()
    await drain(real_db.database)
    event = await watching.until_event("sprint.changed")
    assert event.data == {"space_id": space, "sprint_id": sprint["id"]}
    await not_in.expect_nothing()

    removed = await owner.client.delete(f"/api/spaces/{space}/members/user/{member.id}")
    assert removed.status_code == 204
    await drain(real_db.database)
    await watching.settle()
    started = await owner.client.post(f"/api/sprints/{sprint['id']}/start", json={"version": 1})
    assert started.status_code == 200, started.text
    await drain(real_db.database)
    await watching.expect_nothing()
    await not_in.expect_nothing()
    for stream in (watching, not_in):
        await stream.close()
