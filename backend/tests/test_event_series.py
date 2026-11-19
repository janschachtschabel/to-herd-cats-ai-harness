"""Changing and deleting series (plan M10 task 3b, decision 6, I4 to I6): one occurrence
(`scope=this`: an override, or an EXDATE when deleting), this and the following
(`scope=following`: the series is split, a counted one keeps its total), or all
(`scope=all`: the series row; when its start moves, deleted occurrences and overrides
move with it; a new rule drops what it no longer names and says how much, also as a
dry run). Occurrences are named by their wall time, as the window gives it."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calendars import series_split
from app.modules.calendars.event_models import CalendarEvent
from tests.factories import MakeUser
from tests.factories_calendar import logged_in, new_calendar, new_event, window
from tests.factories_spaces import MakeSpace
from tests.test_event_writes import delete, patch

NOV = ("2026-11-16T00:00:00Z", "2027-01-31T00:00:00Z")


async def _calendar(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> tuple[AsyncClient, str]:
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    return client, (await new_calendar(client, space.id, "Team"))["id"]


async def _weekly(
    client: AsyncClient, calendar_id: str, rule: str, **fields: Any
) -> dict[str, Any]:
    """A series on Mondays from 23 November 2026, 09:00 to 10:00 in Berlin."""
    return await new_event(
        client,
        calendar_id,
        starts_at="2026-11-23T09:00:00+01:00",
        ends_at="2026-11-23T10:00:00+01:00",
        location="Raum 1",
        rrule=rule,
        **fields,
    )


async def _read(client: AsyncClient, event: dict[str, Any]) -> dict[str, Any]:
    r = await client.get(f"/api/events/{event['id']}")
    assert r.status_code == 200, r.text
    read: dict[str, Any] = r.json()
    return read


def _ok(r: Any) -> dict[str, Any]:
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _code(r: Any) -> tuple[int, str]:
    return r.status_code, r.json()["error"]["code"]


def _starts(items: list[dict[str, Any]]) -> list[tuple[str, str | None]]:
    return [(o["start"], o["title"]) for o in items]


async def test_scope_this_adds_an_override_and_keeps_the_series(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await _weekly(client, calendar_id, "FREQ=WEEKLY;COUNT=4")
    this = {"scope": "this", "occurrence": "2026-11-30T09:00:00"}
    changed = _ok(
        await patch(
            client,
            made,
            title="Verschoben",
            starts_at="2026-11-30T14:00:00+01:00",
            ends_at="2026-11-30T15:30:00+01:00",
            query=this,
        )
    )
    override = changed["event"]
    assert override["id"] != made["id"]
    assert (override["series_id"], override["recurrence_id"]) == (made["id"], "2026-11-30T09:00:00")
    assert (override["title"], override["location"], override["rrule"]) == (
        "Verschoben",
        "Raum 1",  # copied from the series
        None,
    )
    assert (override["starts_at"], override["uid"], override["version"]) == (
        "2026-11-30T13:00:00Z",
        made["uid"],
        1,
    )
    master = await _read(client, made)
    assert (master["version"], master["title"], master["exdates"]) == (1, "Termin", [])
    assert _starts(await window(client, *NOV)) == [
        ("2026-11-23T08:00:00Z", "Termin"),
        ("2026-11-30T13:00:00Z", "Verschoben"),
        ("2026-12-07T08:00:00Z", "Termin"),
        ("2026-12-14T08:00:00Z", "Termin"),
    ]
    again = await patch(client, made, title="Noch einmal", query=this)
    assert _code(again) == (409, "event.occurrence_overridden")
    # The override is changed as an event of its own, never as a series.
    assert _ok(await patch(client, override, title="Später"))["event"]["title"] == "Später"
    refused = [
        await patch(client, override | {"version": 2}, rrule="FREQ=DAILY"),
        await patch(client, override | {"version": 2}, title="X", query=this),
        await patch(
            client, made, rrule="FREQ=DAILY", query={**this, "occurrence": "2026-12-07T09:00:00"}
        ),
        await patch(client, made, title="X", query={"scope": "this"}),
        await patch(client, made, title="X", query={**this, "occurrence": "2026-12-01T09:00:00"}),
        await patch(client, made, title="X", query={**this, "occurrence": "30.11.2026"}),
        await patch(
            client, made, title="X", query={**this, "occurrence": "2026-12-07T09:00:00+01:00"}
        ),
    ]
    assert [_code(r) for r in refused] == [
        (422, "event.scope_invalid"),
        (422, "event.scope_invalid"),
        (422, "event.scope_invalid"),
        (422, "event.occurrence_required"),
        (422, "event.occurrence_unknown"),
        (422, "event.occurrence_unknown"),
        (422, "event.occurrence_unknown"),
    ]
    single = await new_event(client, calendar_id)
    assert _code(await patch(client, single, title="X", query=this)) == (422, "event.scope_invalid")


async def test_deleting_one_occurrence_adds_an_exdate(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await _weekly(client, calendar_id, "FREQ=WEEKLY;COUNT=4")
    this = {"scope": "this", "occurrence": "2026-11-30T09:00:00"}
    assert (await delete(client, made, **this)).status_code == 204
    master = await _read(client, made)
    assert (master["exdates"], master["version"]) == (["2026-11-30T09:00:00"], 2)
    assert _code(await delete(client, master, **this)) == (422, "event.occurrence_unknown")
    override = _ok(
        await patch(
            client, master, title="Anders", query={**this, "occurrence": "2026-12-07T09:00:00"}
        )
    )["event"]
    # Deleting an override deletes its occurrence: an EXDATE, the override a tombstone.
    assert (await delete(client, override)).status_code == 204
    assert (await client.get(f"/api/events/{override['id']}")).status_code == 404
    master = await _read(client, made)
    assert (master["exdates"], master["version"]) == (
        ["2026-11-30T09:00:00", "2026-12-07T09:00:00"],
        3,
    )
    assert _starts(await window(client, *NOV)) == [
        ("2026-11-23T08:00:00Z", "Termin"),
        ("2026-12-14T08:00:00Z", "Termin"),
    ]
    last = {"scope": "this", "occurrence": "2026-12-14T09:00:00"}
    assert (await delete(client, master, **last)).status_code == 204
    assert (await _read(client, made))["recurs_until"] == "2026-11-23T09:00:00Z"


async def test_moving_a_series_keeps_its_deleted_occurrences_deleted(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """09:00 → 10:00 across the spring clock change: EXDATEs, RDATEs and the recurrence
    ids of overrides move by the same wall-time difference; nothing comes back, no
    override is dropped."""
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(
        client,
        calendar_id,
        starts_at="2027-03-15T09:00:00+01:00",
        ends_at="2027-03-15T10:00:00+01:00",
        rrule="FREQ=WEEKLY;COUNT=4",
        rdates=["2027-04-20T09:00:00"],
    )
    assert (
        await delete(client, made, scope="this", occurrence="2027-03-22T09:00:00")
    ).status_code == 204
    moved = _ok(
        await patch(
            client,
            made | {"version": 2},
            title="Eigen",
            starts_at="2027-03-29T15:00:00+02:00",
            ends_at="2027-03-29T16:00:00+02:00",
            query={"scope": "this", "occurrence": "2027-03-29T09:00:00"},
        )
    )["event"]
    changed = _ok(
        await patch(
            client,
            made | {"version": 2},
            starts_at="2027-03-15T10:00:00+01:00",
            ends_at="2027-03-15T11:00:00+01:00",
        )
    )
    assert (changed["dropped_overrides"], changed["dropped_exdates"]) == (0, 0)
    master = changed["event"]
    assert (master["exdates"], master["rdates"], master["version"]) == (
        ["2027-03-22T10:00:00"],
        ["2027-04-20T10:00:00"],
        3,
    )
    override = await _read(client, moved)
    assert (override["recurrence_id"], override["starts_at"], override["version"]) == (
        "2027-03-29T10:00:00",
        "2027-03-29T13:00:00Z",  # its own time stays
        2,
    )
    assert _starts(await window(client, "2027-03-01T00:00:00Z", "2027-05-01T00:00:00Z")) == [
        ("2027-03-15T09:00:00Z", "Termin"),
        ("2027-03-29T13:00:00Z", "Eigen"),
        ("2027-04-05T08:00:00Z", "Termin"),  # summer time: 10:00 is 08:00 UTC
        ("2027-04-20T08:00:00Z", "Termin"),
    ]


async def test_a_rule_change_reports_what_it_drops(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await _weekly(
        client,
        calendar_id,
        "FREQ=WEEKLY;COUNT=6",
        exdates=["2026-11-30T09:00:00", "2026-12-07T09:00:00"],
    )
    overrides = [
        _ok(
            await patch(
                client,
                made,
                title=f"Woche {week}",
                query={"scope": "this", "occurrence": f"2026-12-{day}T09:00:00"},
            )
        )["event"]
        for week, day in ((4, 14), (5, 21))
    ]
    every_other = {"rrule": "FREQ=WEEKLY;INTERVAL=2;COUNT=3"}  # 23 Nov, 7 and 21 Dec
    dry = _ok(await patch(client, made, query={"dry_run": "true"}, **every_other))
    assert (dry["dropped_overrides"], dry["dropped_exdates"]) == (1, 1)
    assert (dry["event"]["rrule"], dry["event"]["version"]) == ("FREQ=WEEKLY;COUNT=6", 1)
    unchanged = await _read(client, made)
    assert (unchanged["rrule"], unchanged["version"], len(unchanged["exdates"])) == (
        "FREQ=WEEKLY;COUNT=6",
        1,
        2,
    )
    assert [o["title"] for o in await window(client, *NOV)] == [
        "Termin",
        "Woche 4",
        "Woche 5",
        "Termin",
    ]
    changed = _ok(await patch(client, made, **every_other))
    assert (changed["dropped_overrides"], changed["dropped_exdates"]) == (1, 1)
    assert (changed["event"]["exdates"], changed["event"]["version"]) == (
        ["2026-12-07T09:00:00"],
        2,
    )
    assert (await client.get(f"/api/events/{overrides[0]['id']}")).status_code == 404
    assert _starts(await window(client, *NOV)) == [
        ("2026-11-23T08:00:00Z", "Termin"),
        ("2026-12-21T08:00:00Z", "Woche 5"),
    ]
    overlapping = await patch(
        client, changed["event"], rrule="FREQ=DAILY", ends_at="2026-11-24T12:00:00+01:00"
    )
    assert _code(overlapping) == (422, "event.series_overlaps")


async def test_scope_following_splits_the_series(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await _weekly(client, calendar_id, "FREQ=WEEKLY")
    changed = _ok(
        await patch(
            client,
            made,
            title="Neu",
            starts_at="2026-12-07T11:00:00+01:00",
            ends_at="2026-12-07T12:00:00+01:00",
            query={"scope": "following", "occurrence": "2026-12-07T09:00:00"},
        )
    )
    new = changed["event"]
    assert new["id"] != made["id"] and new["uid"] != made["uid"]
    assert (new["title"], new["location"], new["rrule"], new["series_id"]) == (
        "Neu",
        "Raum 1",
        "FREQ=WEEKLY;BYDAY=MO",  # the weekday DTSTART gave, written out (R3b-4)
        None,
    )
    assert (new["starts_at"], new["recurs_until"]) == ("2026-12-07T10:00:00Z", None)
    old = await _read(client, made)
    assert (old["rrule"], old["recurs_until"], old["version"]) == (
        "FREQ=WEEKLY;UNTIL=20261207T075959Z",  # a second before 09:00 in Berlin
        "2026-11-30T09:00:00Z",
        2,
    )
    assert _starts(await window(client, "2026-11-16T00:00:00Z", "2026-12-28T00:00:00Z")) == [
        ("2026-11-23T08:00:00Z", "Termin"),
        ("2026-11-30T08:00:00Z", "Termin"),
        ("2026-12-07T10:00:00Z", "Neu"),
        ("2026-12-14T10:00:00Z", "Neu"),
        ("2026-12-21T10:00:00Z", "Neu"),
    ]


async def test_splitting_a_counted_series_keeps_the_total(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(
        client,
        calendar_id,
        starts_at="2026-11-23T09:00:00+01:00",
        ends_at="2026-11-23T10:00:00+01:00",
        rrule="FREQ=DAILY;COUNT=10",
        exdates=["2026-11-24T09:00:00"],  # deleted occurrences count too
    )
    following = {"scope": "following", "occurrence": "2026-11-26T09:00:00"}  # the 4th
    new = _ok(await patch(client, made, title="Rest", query=following))["event"]
    old = await _read(client, made)
    assert (old["rrule"], old["exdates"]) == (
        "FREQ=DAILY;UNTIL=20261126T075959Z",
        ["2026-11-24T09:00:00"],
    )
    assert (new["rrule"], new["exdates"]) == ("FREQ=DAILY;COUNT=7", [])
    titles = [o["title"] for o in await window(client, *NOV)]
    assert titles == ["Termin"] * 2 + ["Rest"] * 7  # 3 + 7 = 10, one of them deleted
    whole_days = await new_event(
        client,
        calendar_id,
        all_day=True,
        starts_at=None,
        ends_at=None,
        time_zone=None,
        first_day="2026-11-23",
        last_day="2026-11-23",
        rrule="FREQ=DAILY;COUNT=5",
    )
    split = {"scope": "following", "occurrence": "2026-11-25T00:00:00"}
    rest = _ok(await patch(client, whole_days, title="Danach", query=split))["event"]
    assert (await _read(client, whole_days))["rrule"] == "FREQ=DAILY;UNTIL=20261124"
    assert (rest["rrule"], rest["first_day"]) == ("FREQ=DAILY;COUNT=3", "2026-11-25")


async def test_later_overrides_and_exdates_move_to_the_new_series(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await _weekly(
        client,
        calendar_id,
        "FREQ=WEEKLY;COUNT=8",
        exdates=["2026-11-30T09:00:00", "2026-12-28T09:00:00"],  # weeks 2 and 6
    )
    early, late = [
        _ok(
            await patch(
                client, made, title=title, query={"scope": "this", "occurrence": occurrence}
            )
        )["event"]
        for title, occurrence in (("Früh", "2026-12-07T09:00:00"), ("Spät", "2026-12-21T09:00:00"))
    ]
    changed = _ok(
        await patch(
            client,
            made,
            starts_at="2026-12-14T10:00:00+01:00",
            ends_at="2026-12-14T11:00:00+01:00",
            query={"scope": "following", "occurrence": "2026-12-14T09:00:00"},  # week 4
        )
    )
    assert (changed["dropped_overrides"], changed["dropped_exdates"]) == (0, 0)
    new = changed["event"]
    assert (new["rrule"], new["exdates"]) == (
        "FREQ=WEEKLY;COUNT=5;BYDAY=MO",
        ["2026-12-28T10:00:00"],
    )
    old = await _read(client, made)
    assert old["exdates"] == ["2026-11-30T09:00:00"]
    stayed, went = await _read(client, early), await _read(client, late)
    assert (stayed["series_id"], stayed["recurrence_id"], stayed["uid"]) == (
        made["id"],
        "2026-12-07T09:00:00",
        made["uid"],
    )
    assert (went["series_id"], went["recurrence_id"], went["uid"]) == (
        new["id"],
        "2026-12-21T10:00:00",
        new["uid"],
    )
    assert _starts(await window(client, *NOV)) == [
        ("2026-11-23T08:00:00Z", "Termin"),
        ("2026-12-07T08:00:00Z", "Früh"),
        ("2026-12-14T09:00:00Z", "Termin"),
        ("2026-12-21T08:00:00Z", "Spät"),
        ("2027-01-04T09:00:00Z", "Termin"),
        ("2027-01-11T09:00:00Z", "Termin"),
    ]


async def test_splitting_at_the_first_occurrence_changes_all(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await _weekly(client, calendar_id, "FREQ=WEEKLY;COUNT=3")
    first = {"scope": "following", "occurrence": "2026-11-23T09:00:00"}
    changed = _ok(await patch(client, made, title="Alle", query=first))["event"]
    assert (changed["id"], changed["title"], changed["rrule"], changed["version"]) == (
        made["id"],
        "Alle",
        "FREQ=WEEKLY;COUNT=3",
        2,
    )
    assert [o["title"] for o in await window(client, *NOV)] == ["Alle"] * 3


async def test_deleting_this_and_the_following_ends_the_series(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await _weekly(client, calendar_id, "FREQ=WEEKLY")
    late = _ok(
        await patch(
            client, made, title="Spät", query={"scope": "this", "occurrence": "2026-12-14T09:00:00"}
        )
    )["event"]
    gone = await delete(client, made, scope="following", occurrence="2026-12-07T09:00:00")
    assert gone.status_code == 204
    old = await _read(client, made)
    assert (old["rrule"], old["version"]) == ("FREQ=WEEKLY;UNTIL=20261207T075959Z", 2)
    assert (await client.get(f"/api/events/{late['id']}")).status_code == 404
    assert len(await window(client, *NOV)) == 2
    first = {"scope": "following", "occurrence": "2026-11-23T09:00:00"}
    assert (await delete(client, old, **first)).status_code == 204
    assert (await client.get(f"/api/events/{made['id']}")).status_code == 404


async def test_deleting_a_series_deletes_its_overrides(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await _weekly(client, calendar_id, "FREQ=WEEKLY;COUNT=3")
    override = _ok(
        await patch(
            client, made, title="X", query={"scope": "this", "occurrence": "2026-11-30T09:00:00"}
        )
    )["event"]
    assert (await delete(client, made)).status_code == 204
    for event in (made, override):
        assert (await client.get(f"/api/events/{event['id']}")).status_code == 404
    assert await window(client, *NOV) == []


async def test_a_split_runs_the_carry_hooks(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, monkeypatch: pytest.MonkeyPatch
) -> None:
    carried: list[tuple[str, str]] = []

    async def _carry(session: AsyncSession, old: CalendarEvent, new: CalendarEvent) -> None:
        carried.append((str(old.id), str(new.id)))

    monkeypatch.setattr(series_split, "CARRY", [_carry])
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await _weekly(client, calendar_id, "FREQ=WEEKLY;COUNT=3")
    following = {"scope": "following", "occurrence": "2026-11-30T09:00:00"}
    dry = await patch(client, made, title="X", query={**following, "dry_run": "true"})
    assert dry.status_code == 200 and carried == []  # a dry run carries nothing
    new = _ok(await patch(client, made, title="X", query=following))["event"]
    assert carried == [(made["id"], new["id"])]


@pytest.mark.parametrize("days", [1, -1])
async def test_moving_a_series_by_a_day_moves_neighbouring_overrides(
    days: int, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """Each override takes the recurrence id its neighbour had: moved one at a time in
    the order that never holds two at one id."""
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(
        client,
        calendar_id,
        starts_at="2026-11-23T09:00:00+01:00",
        ends_at="2026-11-23T10:00:00+01:00",
        rrule="FREQ=DAILY;COUNT=5",
    )
    for day in (24, 25, 26):
        this = {"scope": "this", "occurrence": f"2026-11-{day}T09:00:00"}
        assert (await patch(client, made, title=f"Tag {day}", query=this)).status_code == 200
    start = 23 + days
    changed = _ok(
        await patch(
            client,
            made,
            starts_at=f"2026-11-{start}T09:00:00+01:00",
            ends_at=f"2026-11-{start}T10:00:00+01:00",
        )
    )
    assert (changed["dropped_overrides"], changed["dropped_exdates"]) == (0, 0)
    titles = sorted((o["start"][:10], o["title"]) for o in await window(client, *NOV))
    assert titles == sorted(
        [
            (f"2026-11-{start}", "Termin"),
            ("2026-11-24", "Tag 24"),  # the overrides keep their own times
            ("2026-11-25", "Tag 25"),
            ("2026-11-26", "Tag 26"),
            (f"2026-11-{start + 4}", "Termin"),
        ]
    )


async def test_overrides_and_splits_are_checked_like_new_events(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """The 3a limits hold on every write path: no event over a year and a day, no
    series on top of itself, times in the calendar's years."""
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await _weekly(client, calendar_id, "FREQ=WEEKLY;COUNT=4")
    this = {"scope": "this", "occurrence": "2026-11-30T09:00:00"}
    following = {"scope": "following", "occurrence": "2026-11-30T09:00:00"}
    refused = [
        await patch(client, made, ends_at="2027-12-02T09:00:00+01:00", query=this),
        await patch(client, made, starts_at="2400-01-03T09:00:00+01:00", query=this),
        await patch(
            client, made, rrule="FREQ=DAILY", ends_at="2026-12-01T12:00:00+01:00", query=following
        ),
        await patch(client, made, ends_at="2027-12-02T09:00:00+01:00", query=following),
    ]
    assert [_code(r) for r in refused] == [
        (422, "event.too_long"),
        (422, "event.time_out_of_range"),
        (422, "event.series_overlaps"),
        (422, "event.too_long"),
    ]
    master = await _read(client, made)
    assert (master["version"], master["rrule"]) == (1, "FREQ=WEEKLY;COUNT=4")
    assert len(await window(client, *NOV)) == 4
