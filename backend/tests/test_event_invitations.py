"""Invitations (plan M10 task 4, decisions 3 and 7): attendees are rows on an event,
not copies. An attendee sees the event (only it, never its calendar, space or other
events), answers, and finds it in "my events" (the window with `mine=true`); changing
the attendees needs `calendar.write` in the event's space and full sight, at the
version read. At most 100 attendees; a person without `directory.read` invites only
people who read the event's space; agents count as accepted and start nothing;
addresses are kept and marked not sent."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.run_models import Run
from app.modules.messaging.notification_models import Notification
from tests.factories import MakeUser
from tests.factories_agents import Bench
from tests.factories_calendar import listed, logged_in, new_calendar, new_event, window
from tests.factories_invitations import (
    SPAN,
    answer,
    attendees,
    calendar_handlers,
    invite,
    person,
    put_attendees,
    responses,
    team,
)
from tests.factories_spaces import MakeSpace


def _code(r: Any) -> tuple[int, str]:
    return r.status_code, r.json()["error"]["code"]


async def test_an_attendee_outside_the_space_sees_the_event_and_nothing_else(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    invited = await new_event(t.organiser_client, t.calendar["id"], title="Planung")
    other = await new_event(t.organiser_client, t.calendar["id"], title="Intern")
    await invite(t.organiser_client, invited, person(t.outsider))
    seen = await t.outsider_client.get(f"/api/events/{invited['id']}")
    assert seen.status_code == 200, seen.text
    assert (seen.json()["title"], seen.json()["redacted"]) == ("Planung", False)
    assert [a["principal_id"] for a in await attendees(t.outsider_client, invited["id"])] == [
        str(t.outsider.id)
    ]
    unknown = await t.outsider_client.get(f"/api/events/{uuid.uuid4()}")
    hidden = await t.outsider_client.get(f"/api/events/{other['id']}")
    assert _code(hidden) == _code(unknown) == (404, "event.not_found")
    assert _code(await t.outsider_client.get(f"/api/events/{other['id']}/attendees")) == (
        404,
        "event.not_found",
    )
    assert (await t.outsider_client.get(f"/api/spaces/{t.space.id}")).status_code == 404
    calendars = await t.outsider_client.get(f"/api/spaces/{t.space.id}/calendars")
    assert calendars.status_code == 404
    assert t.calendar["id"] not in [c["id"] for c in await listed(t.outsider_client)]
    for mine in (False, True):
        found = await window(t.outsider_client, *SPAN, mine=mine)
        assert [(o["event_id"], o["title"]) for o in found] == [(invited["id"], "Planung")]
    named = await t.outsider_client.get(
        "/api/calendar/events", params={"from": SPAN[0], "to": SPAN[1], "space_id": str(t.space.id)}
    )
    assert named.status_code == 404


async def test_mine_holds_what_one_organises_or_is_invited_to(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    own = await new_event(t.writer_client, t.calendar["id"], title="Eigen")
    invited = await new_event(t.organiser_client, t.calendar["id"], title="Eingeladen")
    await new_event(t.organiser_client, t.calendar["id"], title="Fremd")
    await invite(t.organiser_client, invited, person(t.writer))
    mine = await window(t.writer_client, *SPAN, mine=True)
    assert sorted(o["event_id"] for o in mine) == sorted([own["id"], invited["id"]])
    assert len(await window(t.writer_client, *SPAN)) == 3


async def test_only_calendar_writers_change_an_event_attendees_only_respond(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    event = await invite(
        t.organiser_client,
        await new_event(t.organiser_client, t.calendar["id"]),
        person(t.reader),
        person(t.outsider),
    )
    for client in (t.reader_client, t.outsider_client):
        refused = await put_attendees(client, event, [person(t.reader)], event["version"])
        assert _code(refused) == (403, "auth.permission_denied")
        assert (await answer(client, event["id"], "accepted")).status_code == 200
    by_writer = await put_attendees(
        t.writer_client, event, [person(t.reader), person(t.writer)], event["version"]
    )
    assert by_writer.status_code == 200, by_writer.text
    assert by_writer.json()["version"] == event["version"] + 1
    assert responses(await attendees(t.organiser_client, event["id"])) == {
        str(t.reader.id): "accepted",  # an attendee kept keeps her answer
        str(t.writer.id): "needs_action",
    }
    assert _code(await answer(t.outsider_client, event["id"], "accepted")) == (
        404,
        "event.not_found",
    )  # no longer invited, and not in the space: as unknown
    assert _code(await answer(t.organiser_client, event["id"], "accepted")) == (
        403,
        "event.not_invited",
    )


async def test_setting_attendees_with_a_stale_version_answers_409(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    event = await new_event(t.organiser_client, t.calendar["id"])
    first = await put_attendees(t.organiser_client, event, [person(t.reader)], event["version"])
    assert first.status_code == 200, first.text
    stale = await put_attendees(t.writer_client, event, [person(t.writer)], event["version"])
    assert _code(stale) == (409, "event.version_conflict")
    assert responses(await attendees(t.organiser_client, event["id"])) == {
        str(t.reader.id): "needs_action"
    }


async def test_a_recurring_invitation_shows_for_every_attendee_in_the_window(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    second = await make_user()
    series = await new_event(
        t.organiser_client, t.calendar["id"], title="Jour fixe", rrule="FREQ=WEEKLY;COUNT=4"
    )
    await invite(t.organiser_client, series, person(t.outsider), person(second))
    for client in (t.outsider_client, await logged_in(make_client, second)):
        found = await window(client, *SPAN)
        assert [o["title"] for o in found] == ["Jour fixe"] * 4
        assert len({o["start"] for o in found}) == 4


async def test_more_than_a_hundred_attendees_are_refused(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    event = await new_event(t.organiser_client, t.calendar["id"])
    many = [{"type": "email", "email": f"p{i}@example.org"} for i in range(101)]
    r = await put_attendees(t.organiser_client, event, many, event["version"])
    assert _code(r) == (422, "validation_failed")  # the schema's bound (max_length)
    ok = await put_attendees(t.organiser_client, event, many[:100], event["version"])
    assert ok.status_code == 200, ok.text
    twice = [person(t.reader), person(t.reader)]
    assert _code(await put_attendees(t.organiser_client, event, twice, ok.json()["version"])) == (
        422,
        "event.attendee_duplicate",
    )


async def test_inviting_needs_directory_read(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    guest, colleague, stranger = await make_user("guest"), await make_user(), await make_user()
    space = await make_space("team", members=[(guest, "editor"), (colleague, "viewer")])
    guest_client = await logged_in(make_client, guest)
    calendar = await new_calendar(
        await logged_in(make_client, await make_user("admin")), space.id, "Team"
    )
    event = await new_event(guest_client, calendar["id"])
    unknown = await put_attendees(
        guest_client, event, [{"type": "user", "id": str(uuid.uuid4())}], event["version"]
    )
    outside = await put_attendees(guest_client, event, [person(stranger)], event["version"])
    assert _code(outside) == _code(unknown) == (422, "event.attendee_unknown")
    ok = await put_attendees(guest_client, event, [person(colleague)], event["version"])
    assert ok.status_code == 200, ok.text  # a reader of the space: one the guest sees


async def test_an_agent_attendee_counts_as_accepted_and_starts_no_run(
    bench: Bench, make_space: MakeSpace, session: AsyncSession
) -> None:
    alice = bench.people.users["alice"]
    space = await make_space("team", members=[(alice, "moderator")])
    calendar = await new_calendar(bench.people.alice, space.id, "Team")
    event = await new_event(bench.people.alice, calendar["id"])
    runs = await session.scalar(select(func.count()).select_from(Run))
    await invite(bench.people.alice, event, {"type": "agent", "id": str(bench.agent.id)})
    await calendar_handlers(session)
    listed_attendees = await attendees(bench.people.alice, event["id"])
    assert [(a["type"], a["response"]) for a in listed_attendees] == [("agent", "accepted")]
    assert listed_attendees[0]["name"] == bench.agent.name
    assert await session.scalar(select(func.count()).select_from(Run)) == runs
    told = (await session.scalars(select(Notification))).all()
    assert all(n.calendar_event_id is None for n in told)


async def test_external_addresses_are_kept_and_marked_not_sent(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    event = await new_event(t.organiser_client, t.calendar["id"])
    await invite(
        t.organiser_client,
        event,
        {"type": "email", "email": "Kim@Example.org", "name": "Kim Muster", "role": "optional"},
        person(t.reader),
    )
    listed_attendees = {a["type"]: a for a in await attendees(t.organiser_client, event["id"])}
    external = listed_attendees["email"]
    assert (external["email"], external["name"], external["role"]) == (
        "Kim@example.org",  # the domain's letter case is not the address's
        "Kim Muster",
        "optional",
    )
    assert (external["response"], external["delivery"]) == ("needs_action", "not_sent")
    assert listed_attendees["user"]["delivery"] == "internal"
    assert listed_attendees["user"]["email"] is None  # people's addresses are never shown
    same = {"type": "email", "email": "kim@example.org"}
    version = (await t.organiser_client.get(f"/api/events/{event['id']}")).json()["version"]
    again = await put_attendees(t.organiser_client, event, [same, same], version)
    assert _code(again) == (422, "event.attendee_duplicate")
