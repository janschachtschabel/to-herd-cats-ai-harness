"""The event window (plan M10 task 3a, decision 6): every occurrence overlapping
`[from, to)` of the events one may list, series expanded in their zone's wall time,
paged by (start, id); all-day events float on their days, compared in the viewer's
zone (`tz`), so viewers in UTC+13 and UTC−11 see the day's event and not the
neighbours'; at most 2,000 occurrences per call."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import REGISTRY
from app.core.pagination import PageParams
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.window import list_window
from app.modules.users.models import User
from tests.factories import MakeUser
from tests.factories_calendar import actor_of, logged_in, new_calendar, new_event, window
from tests.factories_spaces import MakeSpace


async def _calendar(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> tuple[AsyncClient, dict[str, Any], User]:
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    return client, await new_calendar(client, space.id, "Team"), author


def _starts(items: list[dict[str, Any]]) -> list[str]:
    return [i["start"] for i in items]


async def test_window_lists_occurrences_across_a_dst_change(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _calendar(make_client, make_user, make_space)
    berlin = await new_event(
        client,
        calendar["id"],
        starts_at="2026-10-23T09:00:00+02:00",
        ends_at="2026-10-23T09:30:00+02:00",
        rrule="FREQ=DAILY",
    )
    items = await window(client, "2026-10-24T00:00:00Z", "2026-10-27T00:00:00Z")
    assert _starts(items) == [
        "2026-10-24T07:00:00Z",
        "2026-10-25T08:00:00Z",  # 09:00 stays 09:00 in Berlin after the change
        "2026-10-26T08:00:00Z",
    ]
    assert [i["end"] for i in items][1] == "2026-10-25T08:30:00Z"
    assert [i["recurrence_id"] for i in items] == [
        "2026-10-24T09:00:00",
        "2026-10-25T09:00:00",
        "2026-10-26T09:00:00",
    ]
    assert {i["event_id"] for i in items} == {berlin["id"]}
    assert all(i["recurring"] for i in items)
    york = await new_event(
        client,
        calendar["id"],
        starts_at="2026-03-06T02:30:00-05:00",
        ends_at="2026-03-06T03:30:00-05:00",
        tzid="America/New_York",
        rrule="FREQ=DAILY;COUNT=4",
    )
    items = await window(client, "2026-03-06T00:00:00Z", "2026-03-10T00:00:00Z")
    assert [(i["start"], i["recurrence_id"]) for i in items if i["event_id"] == york["id"]] == [
        ("2026-03-06T07:30:00Z", "2026-03-06T02:30:00"),
        ("2026-03-07T07:30:00Z", "2026-03-07T02:30:00"),
        ("2026-03-08T07:30:00Z", "2026-03-08T02:30:00"),  # 02:30 in the gap: 03:30 EDT
        ("2026-03-09T06:30:00Z", "2026-03-09T02:30:00"),
    ]
    single = await new_event(
        client, calendar["id"], starts_at="2026-03-07T12:00:00Z", ends_at="2026-03-07T12:00:00Z"
    )  # zero length
    items = await window(client, "2026-03-07T12:00:00Z", "2026-03-07T13:00:00Z")
    assert [(i["event_id"], i["recurrence_id"], i["recurring"]) for i in items] == [
        (single["id"], None, False)
    ]


async def test_window_pages_by_start_and_id(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _calendar(make_client, make_user, make_space)
    for _ in range(3):  # three series on the same instants: ties broken by the id
        await new_event(client, calendar["id"], rrule="FREQ=DAILY;COUNT=50")
    span = ("2026-11-01T00:00:00Z", "2027-02-01T00:00:00Z")
    for limit in (100, 7):
        items = await window(client, *span, limit=limit)
        keys = [(i["start"], i["event_id"]) for i in items]
        assert len(keys) == 150 == len(set(keys)), limit
        assert keys == sorted(keys), limit
    first = await client.get(
        "/api/calendar/events", params={"from": span[0], "to": span[1], "limit": 100}
    )
    assert len(first.json()["items"]) == 100 and first.json()["next_cursor"]
    r = await client.get(
        "/api/calendar/events", params={"from": span[0], "to": span[1], "cursor": "kaputt"}
    )
    assert r.status_code == 422


async def test_all_day_events_show_for_viewers_far_east_and_west(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _calendar(make_client, make_user, make_space)
    days = {}
    for day in ("2026-11-18", "2026-11-19", "2026-11-20"):
        days[day] = await new_event(
            client,
            calendar["id"],
            all_day=True,
            starts_at=None,
            ends_at=None,
            tzid=None,
            first_day=day,
            last_day=day,
        )
    yearly = await new_event(
        client,
        calendar["id"],
        all_day=True,
        starts_at=None,
        ends_at=None,
        tzid=None,
        first_day="2020-11-19",
        last_day="2020-11-19",
        rrule="FREQ=YEARLY",
    )
    expected = {days["2026-11-19"]["id"], yearly["id"]}
    viewers = [
        # 19 November 2026 from 00:00 to 24:00 of the viewer's zone
        ("Pacific/Tongatapu", "2026-11-18T11:00:00Z", "2026-11-19T11:00:00Z"),  # UTC+13
        ("Pacific/Pago_Pago", "2026-11-19T11:00:00Z", "2026-11-20T11:00:00Z"),  # UTC−11
        ("Pacific/Kiritimati", "2026-11-18T10:00:00Z", "2026-11-19T10:00:00Z"),  # UTC+14
        ("UTC", "2026-11-19T00:00:00Z", "2026-11-20T00:00:00Z"),
    ]
    for tz, start, end in viewers:
        items = await window(client, start, end, tz=tz)
        assert {i["event_id"] for i in items} == expected, tz
        mine = next(i for i in items if i["event_id"] == days["2026-11-19"]["id"])
        assert (mine["start"], mine["end"], mine["all_day"]) == (
            "2026-11-19T00:00:00Z",
            "2026-11-20T00:00:00Z",
            True,
        )
    r = await client.get(
        "/api/calendar/events",
        params={"from": viewers[0][1], "to": viewers[0][2], "tz": "Mars/Olympus"},
    )
    assert (r.status_code, r.json()["error"]["code"]) == (422, "calendar.invalid_time_zone")


async def test_a_tentative_event_is_listed_as_tentative(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _calendar(make_client, make_user, make_space)
    await new_event(client, calendar["id"], status="tentative", rrule="FREQ=DAILY;COUNT=2")
    items = await window(client, "2026-11-23T00:00:00Z", "2026-11-25T00:00:00Z")
    assert [i["status"] for i in items] == ["tentative", "tentative"]


async def test_a_cancelled_event_is_listed_as_cancelled(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _calendar(make_client, make_user, make_space)
    await new_event(client, calendar["id"], status="cancelled", busy=False)
    items = await window(client, "2026-11-23T00:00:00Z", "2026-11-24T00:00:00Z")
    assert [(i["status"], i["busy"]) for i in items] == [("cancelled", False)]


def _too_dense() -> float:
    return REGISTRY.get_sample_value("herd_calendar_window_too_dense_total") or 0.0


async def test_a_window_with_too_many_occurrences_is_refused_and_counted(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _calendar(make_client, make_user, make_space)
    for _ in range(3):
        await new_event(client, calendar["id"], rrule="FREQ=DAILY")
    before = _too_dense()
    r = await client.get(
        "/api/calendar/events",
        params={"from": "2026-11-23T00:00:00Z", "to": "2028-11-23T00:00:00Z"},
    )
    assert (r.status_code, r.json()["error"]["code"]) == (422, "calendar.window_too_dense")
    assert _too_dense() == before + 1
    ok = await window(client, "2026-11-23T00:00:00Z", "2027-06-01T00:00:00Z")  # 3 × 190
    assert len(ok) == 3 * 190


async def test_window_bounds_are_checked(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, _, _ = await _calendar(make_client, make_user, make_space)
    for params in (
        {"from": "2026-11-24T00:00:00Z", "to": "2026-11-23T00:00:00Z"},
        {"from": "2026-11-23T00:00:00Z", "to": "2026-11-23T00:00:00Z"},
    ):
        r = await client.get("/api/calendar/events", params=params)
        assert (r.status_code, r.json()["error"]["code"]) == (422, "calendar.invalid_window")
    for params in (
        {"from": "2026-11-23T00:00:00", "to": "2026-11-24T00:00:00Z"},  # naive
        {"to": "2026-11-24T00:00:00Z"},
        {"from": "2026-11-23T00:00:00Z", "to": "2026-11-24T00:00:00Z", "limit": 101},
    ):
        assert (await client.get("/api/calendar/events", params=params)).status_code == 422
    for start, end in (
        ("0001-01-01T00:00:00Z", "2026-11-24T00:00:00Z"),
        ("2026-11-23T00:00:00Z", "9999-12-31T00:00:00Z"),
        ("1899-12-31T23:59:59+00:00", "1900-01-02T00:00:00Z"),
        ("2399-12-31T00:00:00Z", "2400-01-01T00:00:01+00:00"),
        ("0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-12:00"),
    ):
        r = await client.get("/api/calendar/events", params={"from": start, "to": end})
        assert (r.status_code, r.json()["error"]["code"]) == (
            422,
            "calendar.window_out_of_range",
        ), (start, end)
    # The calendar's years, 1900 to 2399, read in the offset each bound was sent with.
    assert await window(client, "1900-01-01T00:00:00+14:00", "2400-01-01T00:00:00-12:00") == []


async def test_window_takes_only_the_calendars_asked_for(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _calendar(make_client, make_user, make_space)
    other = await new_calendar(client, calendar["space_id"], "Andere")
    first = await new_event(client, calendar["id"])
    second = await new_event(client, other["id"])
    span = ("2026-11-23T00:00:00Z", "2026-11-24T00:00:00Z")
    assert {i["event_id"] for i in await window(client, *span)} == {first["id"], second["id"]}
    only = await window(client, *span, calendar_ids=[other["id"]])
    assert [(i["event_id"], i["calendar_id"]) for i in only] == [(second["id"], other["id"])]
    both = await window(client, *span, calendar_ids=[other["id"], calendar["id"]])
    assert len(both) == 2
    assert await window(client, *span, calendar_ids=[str(uuid.uuid4())]) == []


async def test_an_override_takes_the_place_of_its_occurrence(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """Overrides are made in task 3b; the window reads them already."""
    client, calendar, author = await _calendar(make_client, make_user, make_space)
    master = await new_event(client, calendar["id"], rrule="FREQ=WEEKLY;COUNT=4")
    master_row = await session.get(CalendarEvent, uuid.UUID(master["id"]))
    assert master_row is not None
    moved = CalendarEvent(
        org_id=master_row.org_id,
        calendar_id=master_row.calendar_id,
        space_id=master_row.space_id,
        uid=master_row.uid,
        title="Verschoben",
        starts_at=datetime(2026, 11, 30, 13, 0, tzinfo=UTC),
        ends_at=datetime(2026, 11, 30, 14, 0, tzinfo=UTC),
        recurs_until=datetime(2026, 11, 30, 14, 0, tzinfo=UTC),
        tzid="Europe/Berlin",
        series_id=master_row.id,
        recurrence_id=datetime(2026, 11, 30, 10, 0),
        organizer_type=master_row.organizer_type,
        organizer_id=master_row.organizer_id,
    )
    gone = CalendarEvent(  # an override moved out of the window still takes the place
        org_id=master_row.org_id,
        calendar_id=master_row.calendar_id,
        space_id=master_row.space_id,
        uid=master_row.uid,
        title="Weit weg",
        starts_at=datetime(2027, 3, 1, 9, 0, tzinfo=UTC),
        ends_at=datetime(2027, 3, 1, 10, 0, tzinfo=UTC),
        recurs_until=datetime(2027, 3, 1, 10, 0, tzinfo=UTC),
        tzid="Europe/Berlin",
        series_id=master_row.id,
        recurrence_id=datetime(2026, 12, 7, 10, 0),
        organizer_type=master_row.organizer_type,
        organizer_id=master_row.organizer_id,
    )
    session.add_all([moved, gone])
    await session.flush()
    items = await window(client, "2026-11-23T00:00:00Z", "2026-12-21T00:00:00Z")
    assert [(i["start"], i["title"], i["event_id"] == master["id"]) for i in items] == [
        ("2026-11-23T09:00:00Z", "Termin", True),
        ("2026-11-30T13:00:00Z", "Verschoben", False),
        ("2026-12-14T09:00:00Z", "Termin", True),
    ]
    await session.execute(
        update(CalendarEvent)
        .where(CalendarEvent.id == moved.id)
        .values(deleted_at=datetime.now(UTC))
    )
    items = await window(client, "2026-11-23T00:00:00Z", "2026-12-21T00:00:00Z")
    assert len(items) == 3  # a deleted override frees its occurrence again
    assert "Verschoben" not in str(items)


async def test_deleted_events_are_neither_listed_nor_read(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar, _ = await _calendar(make_client, make_user, make_space)
    made = await new_event(client, calendar["id"], uid="weg@example.com")
    await session.execute(
        update(CalendarEvent)
        .where(CalendarEvent.id == uuid.UUID(made["id"]))
        .values(deleted_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    assert await window(client, "2026-11-23T00:00:00Z", "2026-11-24T00:00:00Z") == []
    assert (await client.get(f"/api/events/{made['id']}")).status_code == 404
    await new_event(client, calendar["id"], uid="weg@example.com")  # a tombstone blocks no UID


async def test_mine_is_what_one_organises_across_calendars(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    author, other = await make_user(), await make_user()
    space = await make_space("team", members=[(author, "moderator"), (other, "editor")])
    client = await logged_in(make_client, author)
    calendar = await new_calendar(client, space.id)
    mine = await new_event(client, calendar["id"])
    theirs = await new_event(await logged_in(make_client, other), calendar["id"])
    actor = await actor_of(session, author)
    start = datetime(2026, 11, 23, tzinfo=UTC)
    common: dict[str, Any] = {
        "start": start,
        "end": start + timedelta(days=1),
        "calendar_ids": None,
        "space_id": None,
        "query": None,
        "params": PageParams(),
    }
    every = await list_window(session, actor, mine=False, **common)
    assert {str(o.event_id) for o in every.items} == {mine["id"], theirs["id"]}
    only = await list_window(session, actor, mine=True, **common)
    assert [str(o.event_id) for o in only.items] == [mine["id"]]
