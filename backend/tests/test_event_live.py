"""Calendar changes live (plan M10 task 3a): a new event reaches, as `calendar.changed`
with the space's and the calendar's id only, every stream of a member of the
calendar's space; nobody else, not even an admin outside the space (the calendar lists
hold no space an admin is not in, decision 3). A real server, the real handlers."""

from app.core.principal import SystemRole
from app.modules.users.models import User
from tests.factories import _PASSWORD_HASH
from tests.live_helpers import LiveServer, drain
from tests.live_people import Person, make_person, person, team_channel
from tests.real_db import RealDb


async def _admin(real_db: RealDb, live: LiveServer) -> Person:
    async with real_db.database.session_factory() as session:
        session.add(
            User(
                org_id=real_db.org_id,
                email="admin@real.example.com",
                name="Admin",
                password_hash=_PASSWORD_HASH,
                system_role=SystemRole.ADMIN,
            )
        )
        await session.commit()
    return await person(live, "admin@real.example.com")


async def test_a_new_event_reaches_the_spaces_members_alone(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    outsider = await make_person(real_db, live, "outsider@real.example.com")
    admin = await _admin(real_db, live)
    space, _ = await team_channel(owner, member)
    calendar = await owner.client.post(f"/api/spaces/{space}/calendars", json={"name": "Team"})
    assert calendar.status_code == 201, calendar.text
    calendar_id = calendar.json()["id"]
    await drain(real_db.database)
    watching = await member.stream(real_db)
    not_in, admin_stream = await outsider.stream(real_db), await admin.stream(real_db)
    made = await owner.client.post(
        f"/api/calendars/{calendar_id}/events",
        json={
            "title": "Streng geheimer Termin",
            "starts_at": "2026-11-23T10:00:00Z",
            "ends_at": "2026-11-23T11:00:00Z",
            "visibility": "private",
        },
    )
    assert made.status_code == 201, made.text
    await drain(real_db.database)
    event = await watching.until_event("calendar.changed")
    assert event.data == {"space_id": space, "calendar_id": calendar_id}
    await not_in.expect_nothing()
    await admin_stream.expect_nothing()
    for stream in (watching, not_in, admin_stream):
        await stream.close()
