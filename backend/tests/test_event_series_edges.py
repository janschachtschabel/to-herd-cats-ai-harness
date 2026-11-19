"""Series at their edges (review M10 task 3b, R3b-3, R3b-4, R3b-7, R3b-10, R3b-11,
R3b-12, R3b-13): a split in a fold, a moving split from a gap or an RDATE, a series
with no occurrence left, "the first" as the first live occurrence, dry runs and
versions, one field naming without an audit for a change that changes nothing, the
outbox naming the overrides a delete took, and the hook a new override runs."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.audit.models import CALENDAR_ADMIN_WRITE
from app.modules.calendars import series
from app.modules.calendars.event_models import CalendarEvent
from tests.factories import MakeUser
from tests.factories_calendar import logged_in, new_calendar, new_event, window
from tests.factories_spaces import MakeSpace
from tests.test_event_series import _calendar, _starts
from tests.test_event_series_reach import _outbox
from tests.test_event_writes import _audit, _code, delete, patch

MONDAYS = {
    "starts_at": "2026-11-23T09:00:00+01:00",
    "ends_at": "2026-11-23T10:00:00+01:00",
}
SPAN = ("2026-11-16T00:00:00Z", "2027-01-31T00:00:00Z")


async def test_splitting_at_an_occurrence_in_a_fold_keeps_the_wall_time(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """Daily at 02:30 in Berlin; on 31 October 2027 02:30 comes twice (the first)."""
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(
        client,
        calendar_id,
        starts_at="2027-10-29T02:30:00+02:00",
        ends_at="2027-10-29T03:00:00+02:00",
        rrule="FREQ=DAILY;COUNT=5",
    )
    span = ("2027-10-28T00:00:00Z", "2027-11-04T00:00:00Z")
    before = [start for start, _ in _starts(await window(client, *span))]
    assert before[2:4] == ["2027-10-31T00:30:00Z", "2027-11-01T01:30:00Z"]

    split = await patch(
        client, made, title="Neu", query={"scope": "following", "occurrence": "2027-10-31T02:30:00"}
    )

    assert split.status_code == 200, split.text
    after = _starts(await window(client, *span))
    assert [start for start, _ in after] == before
    assert [title for _, title in after] == ["Termin"] * 2 + ["Neu"] * 3


async def test_moving_this_and_the_following_from_a_gap_moves_each_by_the_wall_time(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """Daily at 02:30 in Berlin, split at the gap on 28 March 2027 and moved to 10:00
    (as the client sends it for that day): that day and every later one at 10:00."""
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(
        client,
        calendar_id,
        starts_at="2027-03-26T02:30:00+01:00",
        ends_at="2027-03-26T03:00:00+01:00",
        rrule="FREQ=DAILY;COUNT=5",
    )
    split = await patch(
        client,
        made,
        starts_at="2027-03-28T10:00:00+02:00",
        ends_at="2027-03-28T10:30:00+02:00",
        query={"scope": "following", "occurrence": "2027-03-28T02:30:00"},
    )

    assert split.status_code == 200, split.text
    starts = [
        s for s, _ in _starts(await window(client, "2027-03-25T00:00:00Z", "2027-04-02T00:00:00Z"))
    ]
    assert starts == [
        "2027-03-26T01:30:00Z",
        "2027-03-27T01:30:00Z",
        "2027-03-28T08:00:00Z",
        "2027-03-29T08:00:00Z",
        "2027-03-30T08:00:00Z",
    ]


async def test_moving_this_and_the_following_from_an_rdate_keeps_the_rule(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """Mondays and one extra Wednesday; from the Wednesday on, one hour later: the
    Wednesday and the Mondays after it, never Wednesdays."""
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(
        client, calendar_id, rrule="FREQ=WEEKLY;COUNT=5", rdates=["2026-12-09T09:00:00"], **MONDAYS
    )
    split = await patch(
        client,
        made,
        starts_at="2026-12-09T10:00:00+01:00",
        ends_at="2026-12-09T11:00:00+01:00",
        query={"scope": "following", "occurrence": "2026-12-09T09:00:00"},
    )

    assert split.status_code == 200, split.text
    new = split.json()["event"]
    assert (new["starts_at"], new["rrule"]) == (
        "2026-12-14T09:00:00Z",
        "FREQ=WEEKLY;COUNT=2;BYDAY=MO",
    )
    assert [s for s, _ in _starts(await window(client, *SPAN))] == [
        "2026-11-23T08:00:00Z",
        "2026-11-30T08:00:00Z",
        "2026-12-07T08:00:00Z",
        "2026-12-09T09:00:00Z",
        "2026-12-14T09:00:00Z",
        "2026-12-21T09:00:00Z",
    ]


async def test_deleting_every_occurrence_deletes_the_series(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(client, calendar_id, rrule="FREQ=WEEKLY;COUNT=2", **MONDAYS)
    first = await delete(client, made, scope="this", occurrence="2026-11-23T09:00:00")
    assert first.status_code == 204
    read = (await client.get(f"/api/events/{made['id']}")).json()

    last = await delete(client, read, scope="this", occurrence="2026-11-30T09:00:00")

    assert last.status_code == 204
    assert (await client.get(f"/api/events/{made['id']}")).status_code == 404
    assert [kind for kind, _ in await _outbox(session, made["id"])][-1] == "calendar_event.deleted"


async def test_the_first_live_occurrence_is_the_first(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """The first Monday is deleted: "this and the following" from the second changes
    the whole series (its times carried to its start), and deleting them deletes it."""
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(client, calendar_id, rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS)
    assert (
        await delete(client, made, scope="this", occurrence="2026-11-23T09:00:00")
    ).status_code == 204
    read = (await client.get(f"/api/events/{made['id']}")).json()
    following = {"scope": "following", "occurrence": "2026-11-30T09:00:00"}

    changed = await patch(
        client,
        read,
        title="Neu",
        starts_at="2026-11-30T10:00:00+01:00",
        ends_at="2026-11-30T11:00:00+01:00",
        query=following,
    )

    assert changed.status_code == 200, changed.text
    assert changed.json()["event"]["id"] == made["id"]
    assert _starts(await window(client, *SPAN)) == [
        ("2026-11-30T09:00:00Z", "Neu"),
        ("2026-12-07T09:00:00Z", "Neu"),
        ("2026-12-14T09:00:00Z", "Neu"),
    ]
    now = changed.json()["event"]
    following["occurrence"] = "2026-11-30T10:00:00"
    assert (await delete(client, now, **following)).status_code == 204
    assert (await client.get(f"/api/events/{made['id']}")).status_code == 404


async def test_dry_runs_and_deleting_one_answer_as_the_real_call(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(client, calendar_id, rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS)
    this = {"scope": "this", "occurrence": "2026-11-30T09:00:00"}
    assert (await patch(client, made, title="A", query=this)).status_code == 200
    dry = {**this, "dry_run": "true"}
    assert _code(await patch(client, made, title="B", query=dry)) == (
        409,
        "event.occurrence_overridden",
    )
    stale = await patch(client, made, version=0, title="B", query={"dry_run": "true"})
    assert _code(stale) == (409, "event.version_conflict")
    assert _code(await delete(client, made, version=0, **this)) == (409, "event.version_conflict")


async def test_one_naming_and_no_audit_for_a_change_that_changes_nothing(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """A member admin changes another's private series: the audit names columns
    (`tzid`, not `time_zone`); sending what is there writes and audits nothing."""
    organiser, admin_user = await make_user(), await make_user(SystemRole.ADMIN)
    space = await make_space("team", members=[(organiser, "moderator"), (admin_user, "editor")])
    owner = await logged_in(make_client, organiser)
    calendar = await new_calendar(owner, space.id, "Team")
    made = await new_event(
        owner, calendar["id"], visibility="private", rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS
    )
    admin = await logged_in(make_client, admin_user)
    this = {"scope": "this", "occurrence": "2026-11-30T09:00:00"}
    moved = await patch(admin, made, time_zone="Europe/Lisbon", query=this)
    assert moved.status_code == 200, moved.text
    same = await patch(admin, made, title="Termin")
    assert same.status_code == 200 and same.json()["event"]["version"] == made["version"]

    writes = [e for e in await _audit(session, admin_user) if e.action == CALENDAR_ADMIN_WRITE]

    assert [(e.details["scope"], e.details["fields"]) for e in writes] == [("this", ["tzid"])]


async def test_a_new_override_runs_the_override_hooks(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """For `scope=this` and for each stray a split leaves with the old part; never in a
    dry run."""
    seen: list[tuple[str, str]] = []

    async def _hook(session: AsyncSession, of: CalendarEvent, override: CalendarEvent) -> None:
        seen.append((str(of.id), str(override.recurrence_id)))

    monkeypatch.setattr(series, "ON_OVERRIDE", [_hook])
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(
        client, calendar_id, rrule="FREQ=WEEKLY;COUNT=4", rdates=["2026-12-09T09:00:00"], **MONDAYS
    )
    this = {"scope": "this", "occurrence": "2026-11-30T09:00:00"}
    assert (
        await patch(client, made, title="X", query={**this, "dry_run": "true"})
    ).status_code == 200
    assert seen == []
    assert (await patch(client, made, title="X", query=this)).status_code == 200
    following = {"scope": "following", "occurrence": "2026-12-09T09:00:00"}
    assert (await patch(client, made, title="Y", query=following)).status_code == 200

    assert seen == [(made["id"], "2026-11-30 09:00:00"), (made["id"], "2026-12-09 09:00:00")]


async def test_deleting_a_series_names_the_overrides_it_took(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(client, calendar_id, rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS)
    this = {"scope": "this", "occurrence": "2026-11-30T09:00:00"}
    override = (await patch(client, made, title="X", query=this)).json()["event"]

    assert (await delete(client, made)).status_code == 204

    assert (await _outbox(session, made["id"]))[-1] == (
        "calendar_event.deleted",
        {"calendar_id": calendar_id, "overrides": [override["id"]]},
    )


async def test_a_change_that_deletes_every_occurrence_deletes_the_series(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(client, calendar_id, rrule="FREQ=WEEKLY;COUNT=2", **MONDAYS)
    gone = ["2026-11-23T09:00:00", "2026-11-30T09:00:00"]

    assert (await patch(client, made, exdates=gone)).status_code == 200

    assert (await client.get(f"/api/events/{made['id']}")).status_code == 404
    assert await window(client, *SPAN) == []
