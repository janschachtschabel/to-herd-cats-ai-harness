"""Zones in the event API (review M10 task 3a, R3a-9): one name, `time_zone`, for the
calendar's, the event's and the viewer's zone; a window's cursor is valid only with
the `time_zone` it was made with (its all-day days depend on it)."""

from typing import Any

from tests.factories import MakeUser
from tests.factories_calendar import logged_in, new_calendar, new_event
from tests.factories_spaces import MakeSpace

SPAN = {"from": "2026-11-23T00:00:00Z", "to": "2026-11-30T00:00:00Z", "limit": 2}


async def test_one_name_for_a_zone_and_a_cursor_bound_to_it(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    calendar = await new_calendar(client, space.id, "Team", time_zone="Asia/Tokyo")
    made = await new_event(client, calendar["id"], time_zone=None, rrule="FREQ=DAILY;COUNT=5")
    assert made["time_zone"] == "Asia/Tokyo" and "tzid" not in made
    url = f"/api/calendars/{calendar['id']}/events"
    old = {"title": "X", "starts_at": made["starts_at"], "ends_at": made["ends_at"]}
    assert (await client.post(url, json={**old, "tzid": "UTC"})).status_code == 422

    first = await client.get("/api/calendar/events", params={**SPAN, "time_zone": "Europe/Berlin"})
    assert first.status_code == 200, first.text
    cursor = first.json()["next_cursor"]
    same = {**SPAN, "time_zone": "Europe/Berlin", "cursor": cursor}
    assert (await client.get("/api/calendar/events", params=same)).status_code == 200
    for other in ({"time_zone": "Pacific/Auckland"}, {}):  # {}: the default, UTC
        r = await client.get("/api/calendar/events", params={**SPAN, **other, "cursor": cursor})
        assert (r.status_code, r.json()["error"]["code"]) == (422, "calendar.cursor_time_zone")
    plain = (await client.get("/api/calendar/events", params=SPAN)).json()["next_cursor"]
    utc = {**SPAN, "time_zone": "UTC", "cursor": plain}
    assert (await client.get("/api/calendar/events", params=utc)).status_code == 200
    r = await client.get("/api/calendar/events", params={**SPAN, "tz": "Mars/Olympus"})
    assert r.status_code == 200  # `tz` is no parameter any more
