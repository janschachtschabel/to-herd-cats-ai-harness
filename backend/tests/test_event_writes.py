"""Changing and deleting events (plan M10 task 3b, decision 3, C2): a write needs
`calendar.write` in the event's space **and** full sight of it; with "busy" sight every
attempt answers 403 `event.private`, and only the organiser or an admin (on the named
way) changes `visibility`. Every write names the version it read (409
`event.version_conflict`); no answer carries content the caller may not see; an event
one may not see answers like an unknown id. A write by admin power alone is audited
(`calendar.admin_write`); an admin's refused write keeps its audit entries
(`test_event_write_audit.py`, on real commits)."""

import uuid
from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.outbox import Event, EventOutbox
from app.core.principal import SystemRole
from app.modules.audit.models import (
    CALENDAR_ADMIN_WRITE,
    AuditLog,
)
from app.modules.calendars.live import live_event
from app.modules.spaces.models import Space
from app.modules.users.models import User
from tests.factories import MakeUser
from tests.factories_calendar import SECRET, logged_in, new_calendar, new_event, window
from tests.factories_spaces import MakeSpace

SPAN = ("2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z")


async def patch(
    client: AsyncClient, event: dict[str, Any], version: int | None = None, **body: Any
) -> Response:
    query = body.pop("query", {})
    payload = {"version": event["version"] if version is None else version, **body}
    return await client.patch(f"/api/events/{event['id']}", params=query, json=payload)


async def delete(
    client: AsyncClient, event: dict[str, Any], version: int | None = None, **query: Any
) -> Response:
    params = {"version": event["version"] if version is None else version, **query}
    return await client.delete(f"/api/events/{event['id']}", params=params)


def _code(r: Response) -> tuple[int, str]:
    return r.status_code, r.json()["error"]["code"]


@dataclass
class Team:
    space: Space
    calendar: dict[str, Any]
    organiser: User
    writer: User
    viewer: User
    organiser_client: AsyncClient
    writer_client: AsyncClient
    viewer_client: AsyncClient


async def _team(make_client: Any, make_user: MakeUser, make_space: MakeSpace) -> Team:
    organiser, writer, viewer = [await make_user() for _ in range(3)]
    space = await make_space(
        "team", members=[(organiser, "moderator"), (writer, "editor"), (viewer, "viewer")]
    )
    organiser_client = await logged_in(make_client, organiser)
    return Team(
        space=space,
        calendar=await new_calendar(organiser_client, space.id, "Team"),
        organiser=organiser,
        writer=writer,
        viewer=viewer,
        organiser_client=organiser_client,
        writer_client=await logged_in(make_client, writer),
        viewer_client=await logged_in(make_client, viewer),
    )


async def _secret(team: Team, **fields: Any) -> dict[str, Any]:
    return await new_event(
        team.organiser_client,
        team.calendar["id"],
        title=f"{SECRET}-Titel",
        location=f"{SECRET}-Ort",
        description=f"{SECRET}-Text",
        visibility="private",
        **fields,
    )


async def _audit(session: AsyncSession, user: User) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.actor_id == user.id).order_by(AuditLog.created_at)
    return list((await session.scalars(stmt)).all())


async def test_changing_an_event_shows_what_was_stored(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    made = await new_event(team.writer_client, team.calendar["id"], title="Alt")
    r = await patch(
        team.organiser_client,
        made,
        title="Neu",
        location="Raum 2",
        starts_at="2026-11-23T14:00:00+01:00",
        ends_at="2026-11-23T15:30:00+01:00",
        status="tentative",
    )
    assert r.status_code == 200, r.text
    changed = r.json()
    assert (changed["dropped_overrides"], changed["dropped_exdates"]) == (0, 0)
    event = changed["event"]
    assert (event["title"], event["location"], event["status"]) == ("Neu", "Raum 2", "tentative")
    assert (event["starts_at"], event["ends_at"]) == (
        "2026-11-23T13:00:00Z",
        "2026-11-23T14:30:00Z",
    )
    assert (event["version"], event["time_zone"], event["redacted"]) == (2, "Europe/Berlin", False)
    read = (await team.viewer_client.get(f"/api/events/{made['id']}")).json()
    assert (read["title"], read["version"], read["organizer"]["id"]) == (
        "Neu",
        2,
        str(team.writer.id),
    )  # the organiser stays whoever made it


async def test_a_change_is_checked_like_a_new_event(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    made = await new_event(team.organiser_client, team.calendar["id"])
    cases: list[tuple[dict[str, Any], tuple[int, str]]] = [
        ({"ends_at": "2026-11-23T08:00:00+01:00"}, (422, "event.invalid_time")),
        ({"time_zone": "Mars/Olympus"}, (422, "event.invalid_time_zone")),
        ({"rrule": "FREQ=HOURLY"}, (422, "event.rrule_unsupported")),
        ({"ends_at": "2027-11-30T10:00:00+01:00"}, (422, "event.too_long")),
        (
            {"rrule": "FREQ=DAILY", "ends_at": "2026-11-24T12:00:00+01:00"},
            (422, "event.series_overlaps"),
        ),
        ({"title": None}, (422, "validation_failed")),
        ({"title": "   "}, (422, "validation_failed")),
        ({"all_day": True}, (422, "event.invalid_time")),  # all-day needs its days
    ]
    for body, expected in cases:
        assert _code(await patch(team.organiser_client, made, **body)) == expected, body
    whole_day = await patch(
        team.organiser_client, made, all_day=True, first_day="2026-11-24", last_day="2026-11-25"
    )
    assert whole_day.status_code == 200, whole_day.text
    assert (whole_day.json()["event"]["time_zone"], whole_day.json()["event"]["first_day"]) == (
        None,
        "2026-11-24",
    )


async def test_deleting_an_event_leaves_it_unseen(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    made = await new_event(team.organiser_client, team.calendar["id"])
    assert (await delete(team.writer_client, made)).status_code == 204
    assert _code(await team.organiser_client.get(f"/api/events/{made['id']}")) == (
        404,
        "event.not_found",
    )
    assert await window(team.organiser_client, *SPAN) == []
    assert _code(await delete(team.writer_client, made)) == (404, "event.not_found")


async def test_writing_needs_calendar_write(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    made = await new_event(team.organiser_client, team.calendar["id"])
    assert _code(await patch(team.viewer_client, made, title="X")) == (
        403,
        "auth.permission_denied",
    )
    assert _code(await delete(team.viewer_client, made)) == (403, "auth.permission_denied")


async def test_a_writer_with_busy_sight_cannot_change_delete_or_unhide_a_private_event(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    hidden = await _secret(team, rrule="FREQ=WEEKLY;COUNT=4")
    writer = team.writer_client
    attempts = [
        await patch(writer, hidden, title="Übernommen"),
        await patch(writer, hidden, visibility="default"),
        await patch(writer, hidden, starts_at="2026-11-23T12:00:00+01:00"),
        await patch(
            writer, hidden, title="X", query={"scope": "this", "occurrence": "2026-11-30T10:00:00"}
        ),
        await patch(
            writer,
            hidden,
            title="X",
            query={"scope": "following", "occurrence": "2026-11-30T10:00:00"},
        ),
        await patch(writer, hidden, 99, title="X"),  # a stale version tells nothing more
        await patch(writer, hidden, title="X", query={"dry_run": "true"}),
        await delete(writer, hidden),
        await delete(writer, hidden, scope="this", occurrence="2026-11-30T10:00:00"),
        await delete(writer, hidden, scope="following", occurrence="2026-11-30T10:00:00"),
    ]
    assert [_code(r) for r in attempts] == [(403, "event.private")] * len(attempts)
    read = (await team.organiser_client.get(f"/api/events/{hidden['id']}")).json()
    assert (read["title"], read["visibility"], read["version"], read["exdates"]) == (
        f"{SECRET}-Titel",
        "private",
        1,
        [],
    )
    assert len(await window(team.organiser_client, *SPAN)) == 2  # 23 and 30 November


async def test_no_write_answer_carries_content_the_caller_may_not_see(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    hidden = await _secret(team, rrule="FREQ=WEEKLY;COUNT=4", uid=f"{SECRET}@example.com")
    outsider = await logged_in(make_client, await make_user())
    answers = [
        await patch(client, hidden, version, title="X", query=query)
        for client in (team.writer_client, team.viewer_client, outsider)
        for version in (1, 99)
        for query in ({}, {"dry_run": "true"}, {"scope": "this", "occurrence": "2026-11-30T10:00"})
    ]
    answers += [
        await delete(client, hidden, version)
        for client in (team.writer_client, team.viewer_client, outsider)
        for version in (1, 99)
    ]
    for r in answers:
        assert r.status_code in (403, 404), r.text
        assert SECRET not in r.text
        assert "current_version" not in r.text
    # The organiser's own answer carries the content; the version conflict only the version.
    stale = await patch(team.organiser_client, hidden, 99, title="X")
    assert _code(stale) == (409, "event.version_conflict")
    assert stale.json()["error"]["details"] == {"current_version": 1}
    assert SECRET not in stale.text


async def test_only_the_organiser_or_an_admin_changes_visibility(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    made = await new_event(team.organiser_client, team.calendar["id"], title="Offen")
    assert _code(await patch(team.writer_client, made, visibility="private")) == (
        403,
        "event.visibility_organiser_only",
    )
    same = await patch(team.writer_client, made, visibility="default", title="Offen 2")
    assert same.status_code == 200, same.text  # naming the same visibility changes nothing
    hidden = await patch(team.organiser_client, same.json()["event"], visibility="private")
    assert hidden.json()["event"]["visibility"] == "private"
    admin_user = await make_user(SystemRole.ADMIN)
    admin = await logged_in(make_client, admin_user)
    shown = await patch(admin, hidden.json()["event"], visibility="default")
    assert shown.status_code == 200, shown.text
    assert (shown.json()["event"]["visibility"], shown.json()["event"]["title"]) == (
        "default",
        "Offen 2",
    )
    assert CALENDAR_ADMIN_WRITE in [e.action for e in await _audit(session, admin_user)]


async def test_a_stale_version_answers_409(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    made = await new_event(team.organiser_client, team.calendar["id"], rrule="FREQ=DAILY;COUNT=5")
    first = await patch(team.writer_client, made, title="Erst")
    assert first.status_code == 200
    occurrence = {"scope": "this", "occurrence": "2026-11-24T10:00:00"}
    for r in (
        await patch(team.organiser_client, made, title="Später"),
        await patch(team.organiser_client, made, title="Später", query=occurrence),
        await delete(team.organiser_client, made),
        await delete(
            team.organiser_client, made, scope="following", occurrence="2026-11-25T10:00:00"
        ),
    ):
        assert _code(r) == (409, "event.version_conflict")
        assert r.json()["error"]["details"] == {"current_version": 2}
    read = (await team.organiser_client.get(f"/api/events/{made['id']}")).json()
    assert (read["title"], read["version"], read["rrule"]) == ("Erst", 2, "FREQ=DAILY;COUNT=5")


async def test_an_unseen_event_answers_like_an_unknown_id_on_writes(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    made = await new_event(team.organiser_client, team.calendar["id"])
    outsider = await logged_in(make_client, await make_user())
    unknown = {**made, "id": str(uuid7())}
    for target in (made, unknown):
        assert _code(await patch(outsider, target, title="X")) == (404, "event.not_found")
        assert _code(await delete(outsider, target)) == (404, "event.not_found")


async def test_a_write_by_admin_power_is_audited_with_ids_and_field_names(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    member_admin = await make_user(SystemRole.ADMIN)
    team2 = await make_space(
        "team", members=[(team.organiser, "moderator"), (member_admin, "editor")]
    )
    calendar2 = await new_calendar(team.organiser_client, team2.id)
    private = await new_event(
        team.organiser_client, calendar2["id"], title="P", visibility="private"
    )
    plain = await new_event(team.organiser_client, calendar2["id"], title="Offen")
    admin = await logged_in(make_client, member_admin)
    assert (await patch(admin, private, title=f"{SECRET}")).status_code == 200
    assert (await patch(admin, plain, title="Offen 2")).status_code == 200  # her own right
    writes = [e for e in await _audit(session, member_admin) if e.action == CALENDAR_ADMIN_WRITE]
    assert [(str(e.target_id), e.target_type) for e in writes] == [
        (private["id"], "calendar_event")
    ]
    assert writes[0].details == {
        "space_id": str(team2.id),
        "calendar_id": calendar2["id"],
        "change": "update",
        "scope": "all",
        "fields": ["title"],
    }
    outside_admin = await make_user(SystemRole.OWNER)
    foreign = await logged_in(make_client, outside_admin)
    target = await new_event(team.organiser_client, team.calendar["id"], title="Team")
    assert (await delete(foreign, target)).status_code == 204
    [deleted] = [
        e for e in await _audit(session, outside_admin) if e.action == CALENDAR_ADMIN_WRITE
    ]
    assert deleted.details == {
        "space_id": str(team.space.id),
        "calendar_id": team.calendar["id"],
        "change": "delete",
        "scope": "all",
        "fields": [],
    }
    assert [e.action for e in await _audit(session, team.writer)] == []
    assert (await patch(team.writer_client, target | {"version": 1}, title="Y")).status_code == 404


async def test_changes_carry_ids_and_field_names_only(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    made = await new_event(team.organiser_client, team.calendar["id"])
    changed = await patch(
        team.organiser_client, made, title=f"{SECRET} neu", description=f"{SECRET}", busy=False
    )
    assert changed.status_code == 200
    assert (await delete(team.organiser_client, changed.json()["event"])).status_code == 204
    rows = (
        await session.scalars(
            select(EventOutbox)
            .where(EventOutbox.subject_id == uuid.UUID(made["id"]))
            .order_by(EventOutbox.id)
        )
    ).all()
    assert [(r.type, r.payload) for r in rows] == [
        ("calendar_event.created", {"calendar_id": team.calendar["id"]}),
        (
            "calendar_event.updated",
            {"calendar_id": team.calendar["id"], "fields": ["busy", "description", "title"]},
        ),
        ("calendar_event.deleted", {"calendar_id": team.calendar["id"]}),
    ]
    for row in rows:
        live = live_event(Event.of(row))
        assert live is not None and live.calendar_id == uuid.UUID(team.calendar["id"])
        assert SECRET not in live.payload()
