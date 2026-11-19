"""Events (plan M10 task 3a, decisions 3 and 5): made in a calendar by its space's
authors (`calendar.write`), checked (times, zone, rule) before anything is stored,
with a zone from the calendar when none is given; one master per UID and calendar;
events that travel (outbox, live) carry ids only."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.calendars.live import live_event
from app.modules.users.models import User
from tests.factories import MakeUser
from tests.factories_calendar import SECRET, logged_in, new_calendar, new_event
from tests.factories_spaces import MakeSpace

BERLIN = {"time_zone": "Europe/Berlin"}


async def _team(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> tuple[AsyncClient, dict[str, Any], User]:
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    return client, await new_calendar(client, space.id, "Team"), author


def _code(r: Any) -> tuple[int, str]:
    return r.status_code, r.json()["error"]["code"]


async def test_create_checks_times_zone_and_rule(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _team(make_client, make_user, make_space)
    url = f"/api/calendars/{calendar['id']}/events"
    base = {
        "title": "X",
        "starts_at": "2026-11-23T10:00:00+01:00",
        "ends_at": "2026-11-23T11:00:00+01:00",
    }
    cases: list[tuple[dict[str, Any], str]] = [
        ({"ends_at": "2026-11-23T09:59:00+01:00"}, "event.invalid_time"),
        ({"time_zone": "Mars/Olympus"}, "event.invalid_time_zone"),
        ({"time_zone": "Europe/Berlin", "rrule": "FREQ=HOURLY"}, "event.rrule_unsupported"),
        ({"rrule": "FREQ=MONTHLY;BYMONTH=2;BYMONTHDAY=30"}, "event.rrule_invalid"),
        ({"rrule": "FREQ=DAILY;UNTIL=24000101T000000Z"}, "event.time_out_of_range"),
        ({"rrule": "FREQ=DAILY;UNTIL=20261231"}, "event.rrule_invalid"),  # a date: all-day
        ({"rrule": "FREQ=DAILY;BYDAY=TU;INTERVAL=7"}, "event.rrule_invalid"),  # never matches
        (
            {"starts_at": "1899-12-31T10:00:00Z", "ends_at": "1899-12-31T11:00:00Z"},
            "event.time_out_of_range",
        ),
        ({"starts_at": "2026-11-23T10:00:00.5+01:00"}, "event.invalid_time"),
        ({"ends_at": "2027-11-24T10:00:01+01:00"}, "event.too_long"),
        ({"rrule": "FREQ=DAILY", "ends_at": "2026-11-24T12:00:00+01:00"}, "event.series_overlaps"),
        ({"first_day": "2026-11-23"}, "event.invalid_time"),  # days belong to all-day ones
        ({"ends_at": None}, "event.invalid_time"),
        ({"rdates": ["2026-11-20T10:00:00"]}, "event.invalid_time"),  # before the start
        ({"rdates": ["2026-11-30T10:00:00+01:00"]}, "event.invalid_time"),  # not a wall time
        ({"all_day": True}, "event.invalid_time"),  # all-day needs days, not instants
        (
            {
                "all_day": True,
                "starts_at": None,
                "ends_at": None,
                "first_day": "2026-11-24",
                "last_day": "2026-11-23",
            },
            "event.invalid_time",
        ),
        (
            {
                "all_day": True,
                "starts_at": None,
                "ends_at": None,
                "first_day": "2026-11-23",
                "last_day": "2026-11-23",
                "time_zone": "Europe/Berlin",
            },
            "event.invalid_time",
        ),
    ]
    for change, code in cases:
        r = await client.post(url, json={**base, **change})
        assert _code(r) == (422, code), (change, r.text)
    for change in (
        {"title": ""},
        {"title": "x" * 301},
        {"location": "x" * 501},
        {"description": "x" * 20_001},
        {"status": "maybe"},
        {"visibility": "secret"},
        {"uid": "x" * 501},
        {"organizer": "someone"},
    ):
        r = await client.post(url, json={**base, **BERLIN, **change})
        assert r.status_code == 422, change


async def test_a_new_event_shows_what_was_stored(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, author = await _team(make_client, make_user, make_space)
    made = await new_event(
        client,
        calendar["id"],
        title="  Planung  ",
        location="Raum 1",
        description="<b>kein HTML</b>",
        rrule="freq=weekly;count=3",
        exdates=["2026-11-30T10:00:00"],
        rdates=["2026-12-24T10:00:00"],
        status="tentative",
    )
    assert {k: v for k, v in made.items() if k not in ("id", "uid")} == {
        "calendar_id": calendar["id"],
        "space_id": calendar["space_id"],
        "series_id": None,
        "recurrence_id": None,
        "title": "Planung",
        "location": "Raum 1",
        "description": "<b>kein HTML</b>",  # plain text, never rendered
        "all_day": False,
        "starts_at": "2026-11-23T09:00:00Z",
        "ends_at": "2026-11-23T10:00:00Z",
        "first_day": None,
        "last_day": None,
        "time_zone": "Europe/Berlin",
        "rrule": "FREQ=WEEKLY;COUNT=3",  # canonical
        "rdates": ["2026-12-24T10:00:00"],
        "exdates": ["2026-11-30T10:00:00"],
        "recurs_until": "2026-12-24T10:00:00Z",  # the RDATE ends last
        "status": "tentative",
        "visibility": "default",
        "busy": True,
        "organizer": {"type": "user", "id": str(author.id)},
        "redacted": False,
        "version": 1,
    }
    assert made["uid"].endswith("@to-herd-cats-ai")
    imported = await new_event(client, calendar["id"], uid="u" * 500)  # as iCalendar keeps
    assert imported["uid"] == "u" * 500
    endless = await new_event(client, calendar["id"], rrule="FREQ=DAILY")
    assert endless["recurs_until"] is None  # endless
    single = await new_event(client, calendar["id"])
    assert single["recurs_until"] == single["ends_at"]  # a single event ends with itself
    fetched = await client.get(f"/api/events/{made['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == made


async def test_an_all_day_event_floats_on_utc_days_and_is_free(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _team(make_client, make_user, make_space)
    r = await client.post(
        f"/api/calendars/{calendar['id']}/events",
        json={
            "title": "Messe",
            "all_day": True,
            "first_day": "2026-11-23",
            "last_day": "2026-11-25",
        },
    )
    assert r.status_code == 201, r.text
    made = r.json()
    assert (made["starts_at"], made["ends_at"], made["time_zone"], made["busy"]) == (
        "2026-11-23T00:00:00Z",
        "2026-11-26T00:00:00Z",
        None,
        False,  # all-day events are free unless said otherwise
    )
    assert (made["first_day"], made["last_day"]) == ("2026-11-23", "2026-11-25")
    busy = await new_event(
        client,
        calendar["id"],
        all_day=True,
        starts_at=None,
        ends_at=None,
        time_zone=None,
        first_day="2026-11-23",
        last_day="2026-11-23",
        busy=True,
        rrule="FREQ=YEARLY;UNTIL=20281123",
    )
    assert (busy["busy"], busy["recurs_until"]) == (True, "2028-11-24T00:00:00Z")


async def test_a_new_event_without_a_zone_takes_the_calendars(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, _, author = await _team(make_client, make_user, make_space)
    space_id = (await client.get("/api/calendars")).json()["items"][0]["space_id"]
    made = await new_calendar(client, space_id, "New York", time_zone="America/New_York")
    assert made["time_zone"] == "America/New_York"
    event = await new_event(client, made["id"], time_zone=None)
    assert event["time_zone"] == "America/New_York"
    r = await client.patch(
        f"/api/calendars/{made['id']}", json={"time_zone": "Asia/Tokyo", "version": 1}
    )
    assert (r.status_code, r.json()["time_zone"]) == (200, "Asia/Tokyo")
    assert (await new_event(client, made["id"], time_zone=None))["time_zone"] == "Asia/Tokyo"
    assert event["time_zone"] == "America/New_York"  # what was made keeps its zone
    # Without a word, a calendar is in Berlin (plan M10 task 3a ruling).
    assert (await new_calendar(client, space_id, "Standard"))["time_zone"] == "Europe/Berlin"
    for body in (
        {"name": "X", "time_zone": "Mars/Olympus"},
        {"name": "X", "time_zone": "localtime"},
    ):
        r = await client.post(f"/api/spaces/{space_id}/calendars", json=body)
        assert _code(r) == (422, "calendar.invalid_time_zone"), body
    r = await client.patch(
        f"/api/calendars/{made['id']}", json={"time_zone": "Nowhere", "version": 2}
    )
    assert _code(r) == (422, "calendar.invalid_time_zone")


async def test_two_masters_with_one_uid_are_refused(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _team(make_client, make_user, make_space)
    await new_event(client, calendar["id"], uid="same@example.com")
    r = await client.post(
        f"/api/calendars/{calendar['id']}/events",
        json={
            "title": "Zwei",
            "uid": "same@example.com",
            "starts_at": "2026-12-01T10:00:00Z",
            "ends_at": "2026-12-01T11:00:00Z",
            **BERLIN,
        },
    )
    assert _code(r) == (409, "event.uid_taken")
    space_id = calendar["space_id"]
    other = await new_calendar(client, space_id, "Andere")
    await new_event(client, other["id"], uid="same@example.com")  # per calendar


async def test_making_an_event_needs_calendar_write(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    moderator, author, viewer, outsider = [await make_user() for _ in range(4)]
    space = await make_space(
        "team", members=[(moderator, "moderator"), (author, "editor"), (viewer, "viewer")]
    )
    calendar = await new_calendar(await logged_in(make_client, moderator), space.id)
    await new_event(await logged_in(make_client, author), calendar["id"])  # an editor writes
    url = f"/api/calendars/{calendar['id']}/events"
    body = {"title": "X", "starts_at": "2026-11-23T10:00:00Z", "ends_at": "2026-11-23T11:00:00Z"}
    r = await (await logged_in(make_client, viewer)).post(url, json=body)
    assert _code(r) == (403, "auth.permission_denied")
    r = await (await logged_in(make_client, outsider)).post(url, json=body)
    assert _code(r) == (404, "calendar.not_found")


async def test_events_carry_ids_only_in_outbox_and_live(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, author = await _team(make_client, make_user, make_space)
    made = await new_event(
        client,
        calendar["id"],
        title=f"{SECRET}-Titel",
        location=f"{SECRET}-Ort",
        description=f"{SECRET}-Text",
        uid=f"{SECRET}@example.com",
        visibility="private",
    )
    rows = (
        await session.scalars(select(EventOutbox).where(EventOutbox.type.like("calendar_event.%")))
    ).all()
    assert [(r.type, r.subject_type, str(r.subject_id), str(r.space_id)) for r in rows] == [
        ("calendar_event.created", "calendar_event", made["id"], calendar["space_id"])
    ]
    assert rows[0].payload == {"calendar_id": calendar["id"]}
    live = live_event(Event.of(rows[0]))
    assert live is not None
    assert live.name == "calendar.changed"
    assert SECRET not in live.payload()
    assert live.frame() == (
        b'event: calendar.changed\ndata: {"space_id":"%s","calendar_id":"%s"}\n\n'
        % (calendar["space_id"].encode(), calendar["id"].encode())
    )
