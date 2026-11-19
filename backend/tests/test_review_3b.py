"""Review of M10 task 3b (changing and deleting events and series): what the review
found, each as a failing test (`.superpowers/sdd/m10/review-task-3b.md`).

- R3b-1: a writer who sees a private override only as "busy" deletes it through its
  series (`scope=this` on the master), against decision 3 (C2).
- R3b-2: hiding a series (`visibility=private`, `scope=all`) leaves its overrides, which
  carry a copy of its content, readable by everyone who reads the calendar.
- R3b-3: "this and following" at an occurrence in a clock-change gap moves every later
  occurrence by the gap (02:30 becomes 03:30 for good).
- R3b-4: "this and following" at an RDATE restarts the rule from the RDATE's weekday:
  the rule's own later occurrences vanish, others appear.
- R3b-5: `EventService.update`/`delete` commit the caller's transaction on a refusal
  (`refusals_keep_audit`), so a caller that is not one HTTP request (an agent's step,
  an import) gets its unfinished work committed.
"""

import uuid
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import select

from app.core.errors import Conflict
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_times import Times
from app.modules.calendars.event_writes import Change, Scope
from app.modules.calendars.events import EventService, NewEvent
from app.modules.users.models import User
from tests.factories import MakeUser, login
from tests.factories_calendar import SECRET, actor_of, new_calendar, new_event, window
from tests.factories_spaces import MakeSpace
from tests.real_db import MakeRealClient, RealDb
from tests.test_event_series import _calendar, _starts
from tests.test_event_write_audit import _team_of
from tests.test_event_writes import _code, _team, delete, patch

SPAN = ("2026-11-01T00:00:00Z", "2027-03-01T00:00:00Z")
MONDAYS = {
    "starts_at": "2026-11-23T09:00:00+01:00",
    "ends_at": "2026-11-23T10:00:00+01:00",
}


async def test_a_writer_with_busy_sight_cannot_delete_a_private_override_through_its_series(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """The organiser makes one occurrence private (an override). The calendar's author
    sees it as "busy" and is refused on the override itself (403 `event.private`), but
    deleting that occurrence through the series succeeds and takes the private event."""
    team = await _team(make_client, make_user, make_space)
    made = await new_event(
        team.organiser_client, team.calendar["id"], rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS
    )
    occurrence = "2026-11-30T09:00:00"
    hidden = await patch(
        team.organiser_client,
        made,
        title=f"{SECRET}-Titel",
        visibility="private",
        query={"scope": "this", "occurrence": occurrence},
    )
    assert hidden.status_code == 200, hidden.text
    override = hidden.json()["event"]
    seen = (await team.writer_client.get(f"/api/events/{override['id']}")).json()
    assert seen["redacted"] is True
    assert _code(await delete(team.writer_client, override)) == (403, "event.private")

    through = await delete(team.writer_client, made, scope="this", occurrence=occurrence)

    assert through.status_code == 403, f"{through.status_code} {through.text}"
    assert _code(through) == (403, "event.private")
    still = await team.organiser_client.get(f"/api/events/{override['id']}")
    assert still.status_code == 200, still.text


async def test_hiding_a_series_hides_its_overrides(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """One occurrence was moved (an override: a copy of the series' content). Then the
    organiser makes the series private. A reader of the calendar must see no content of
    any of its occurrences."""
    team = await _team(make_client, make_user, make_space)
    made = await new_event(
        team.organiser_client,
        team.calendar["id"],
        title=f"{SECRET}-Titel",
        location=f"{SECRET}-Ort",
        rrule="FREQ=WEEKLY;COUNT=4",
        **MONDAYS,
    )
    moved = await patch(
        team.organiser_client,
        made,
        starts_at="2026-11-30T14:00:00+01:00",
        ends_at="2026-11-30T15:00:00+01:00",
        query={"scope": "this", "occurrence": "2026-11-30T09:00:00"},
    )
    assert moved.status_code == 200, moved.text
    hidden = await patch(team.organiser_client, made, visibility="private")
    assert hidden.status_code == 200, hidden.text

    listed = await window(team.viewer_client, *SPAN)

    assert len(listed) == 4
    assert [o["title"] for o in listed] == [None] * 4
    read = await team.viewer_client.get(f"/api/events/{moved.json()['event']['id']}")
    assert SECRET not in read.text


async def test_splitting_at_an_occurrence_in_a_gap_keeps_the_wall_time(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """Daily at 02:30 in Berlin. On 28 March 2027 02:30 does not exist; that occurrence
    starts at 03:30. Renaming "this and following" from it must leave the later ones at
    02:30 (00:30 UTC in summer time), as they were."""
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(
        client,
        calendar_id,
        starts_at="2027-03-25T02:30:00+01:00",
        ends_at="2027-03-25T03:00:00+01:00",
        rrule="FREQ=DAILY;COUNT=8",
    )
    span = ("2027-03-24T00:00:00Z", "2027-04-05T00:00:00Z")
    before = [start for start, _ in _starts(await window(client, *span))]
    assert before[3:5] == ["2027-03-28T01:30:00Z", "2027-03-29T00:30:00Z"]

    split = await patch(
        client,
        made,
        title="Neu",
        query={"scope": "following", "occurrence": "2027-03-28T02:30:00"},
    )

    assert split.status_code == 200, split.text
    after = _starts(await window(client, *span))
    assert [start for start, _ in after] == before
    assert [title for _, title in after] == ["Termin"] * 3 + ["Neu"] * 5


async def test_splitting_at_an_rdate_keeps_the_rule_occurrences(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """Six Mondays and one extra date, a Wednesday (RDATE). Renaming "this and
    following" from the Wednesday must leave every occurrence where it was."""
    client, calendar_id = await _calendar(make_client, make_user, make_space)
    made = await new_event(
        client,
        calendar_id,
        rrule="FREQ=WEEKLY;COUNT=6",
        rdates=["2026-12-09T09:00:00"],
        **MONDAYS,
    )
    before = [start for start, _ in _starts(await window(client, *SPAN))]
    assert len(before) == 7

    split = await patch(
        client,
        made,
        title="Neu",
        query={"scope": "following", "occurrence": "2026-12-09T09:00:00"},
    )

    assert split.status_code == 200, split.text
    after = _starts(await window(client, *SPAN))
    assert [start for start, _ in after] == before
    assert [title for _, title in after] == ["Termin"] * 3 + ["Neu"] * 4


async def test_a_refused_change_does_not_commit_the_callers_transaction(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    """A caller of the service that is not one HTTP request (Task 19's `update_event`
    in a run's step, Task 7b's import) holds work of its own in the transaction. A
    refused change must not commit it."""
    member = await make_real_client()
    await login(member, real_db.member_email)
    team_id = await _team_of(real_db, real_db.member_email)
    calendar_id = uuid.UUID((await new_calendar(member, team_id))["id"])
    made = await new_event(member, calendar_id)
    unfinished = "unfinished@example.com"
    async with real_db.database.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == real_db.member_email))
        assert user is not None
        actor = await actor_of(session, user)
        service = EventService(session)
        start = Times(
            starts_at=datetime.fromisoformat("2026-12-01T10:00:00+00:00"),
            ends_at=datetime.fromisoformat("2026-12-01T11:00:00+00:00"),
        )
        await service.create(actor, calendar_id, NewEvent(title="X", times=start, uid=unfinished))
        with pytest.raises(Conflict):
            await service.update(
                actor,
                uuid.UUID(made["id"]),
                Change({"title": "Y"}),
                scope=Scope.ALL,
                occurrence=None,
                version=99,
            )
        await session.rollback()  # the caller gives its unfinished work up
    async with real_db.database.session_factory() as session:
        kept = await session.scalar(select(CalendarEvent).where(CalendarEvent.uid == unfinished))
    assert kept is None
