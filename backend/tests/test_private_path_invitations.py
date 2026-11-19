"""The private event on the invitation paths (plan M10 review focus 2, task 4): its
content reaches its organiser and its attendees, never a reader of its calendar, on
the notification path (the activity view, the notifications written, the outbox) and
on the live path (`calendar.changed` and `event.invited` carry ids only; the attendee
alone gets `event.invited`)."""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from tests.factories_calendar import SECRET, PrivateEvent
from tests.factories_invitations import attendees, calendar_handlers, invite, notes, person
from tests.live_helpers import LiveServer, drain
from tests.live_people import make_person, team_channel
from tests.real_db import RealDb


async def _activity(client: Any) -> str:
    r = await client.get("/api/activity", params={"limit": 100})
    assert r.status_code == 200, r.text
    return r.text


async def _move(client: Any, event: dict[str, Any]) -> None:
    version = (await client.get(f"/api/events/{event['id']}")).json()["version"]
    r = await client.patch(
        f"/api/events/{event['id']}",
        json={
            "version": version,
            "starts_at": "2026-11-23T12:00:00+01:00",
            "ends_at": "2026-11-23T13:00:00+01:00",
        },
    )
    assert r.status_code == 200, r.text


async def _notification(private_event: PrivateEvent, session: AsyncSession) -> None:
    p = private_event
    # The reader is invited, told, then taken off again: she reads the calendar still.
    await invite(p.organiser_client, p.event, person(p.outsider), person(p.reader))
    await calendar_handlers(session)
    assert SECRET in await _activity(p.outsider_client)  # an attendee sees it in full
    await invite(p.organiser_client, p.event, person(p.outsider))
    await _move(p.organiser_client, p.event)
    answered = await p.outsider_client.post(
        f"/api/events/{p.event['id']}/response",
        json={
            "response": "declined",
            "version": (await p.outsider_client.get(f"/api/events/{p.event['id']}")).json()[
                "version"
            ],
        },
    )
    assert answered.status_code == 200, answered.text
    assert SECRET not in answered.text
    await calendar_handlers(session)
    assert [n.reason for n in await notes(session, p.organiser)] == ["invite_reply"]
    assert await notes(session, p.reader) != []  # her row stays, but she no longer attends
    shown = await _activity(p.reader_client)
    assert SECRET not in shown
    assert json.loads(shown)["items"] == []
    assert (await p.reader_client.get(f"/api/events/{p.event['id']}/attendees")).json()["error"][
        "code"
    ] == "event.private"
    payloads = await session.scalars(
        select(EventOutbox.payload).where(EventOutbox.type.like("calendar_event.%"))
    )
    assert SECRET not in json.dumps(list(payloads.all()))
    assert [a["principal_id"] for a in await attendees(p.organiser_client, p.event["id"])] == [
        str(p.outsider.id)
    ]


async def _live(real_db: RealDb, live: LiveServer) -> None:
    owner = await make_person(real_db, live, "organiser@real.example.com")
    reader = await make_person(real_db, live, "reader@real.example.com")
    guest = await make_person(real_db, live, "guest@real.example.com")
    space, _ = await team_channel(owner, reader)
    calendar = await owner.client.post(f"/api/spaces/{space}/calendars", json={"name": "Team"})
    assert calendar.status_code == 201, calendar.text
    made = await owner.client.post(
        f"/api/calendars/{calendar.json()['id']}/events",
        json={
            "title": f"{SECRET}-Titel",
            "location": f"{SECRET}-Ort",
            "starts_at": "2026-11-23T10:00:00Z",
            "ends_at": "2026-11-23T11:00:00Z",
            "visibility": "private",
        },
    )
    assert made.status_code == 201, made.text
    event = made.json()
    await drain(real_db.database)
    watching: dict[str, Any] = {}
    for who, name in ((reader, "reader"), (guest, "guest")):
        watching[name] = await who.stream(real_db)
    r = await owner.client.put(
        f"/api/events/{event['id']}/attendees",
        json={"version": event["version"], "attendees": [{"type": "user", "id": guest.id}]},
    )
    assert r.status_code == 200, r.text
    await drain(real_db.database)
    invited = await watching["guest"].until_event("event.invited")
    assert invited.data == {"event_id": event["id"]}
    changed = await watching["reader"].until_event("calendar.changed")
    assert set(changed.data) == {"space_id", "calendar_id"}
    await watching["reader"].expect_nothing()  # no `event.invited` for a mere reader
    for stream in watching.values():
        assert SECRET not in "\n".join(stream.raw)
        await stream.close()


async def test_a_private_event_is_only_busy_on_the_notification_path(
    private_event: PrivateEvent, session: AsyncSession
) -> None:
    await _notification(private_event, session)


async def test_a_private_event_is_only_busy_on_the_live_path(
    real_db: RealDb, live: LiveServer
) -> None:
    await _live(real_db, live)
