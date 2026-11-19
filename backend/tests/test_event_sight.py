"""Who sees an event (plan M10 task 3a, decision 3): whoever reads its calendar's space
and its organiser; the content of a private one only its organiser and, on the named
way, admins; every other reader of the calendar gets times and "busy" on every path
(review focus 2). Lists hold for admins as for anyone (C1): another space's events an
admin sees only by naming the space (window with `space_id`, an event by id), which is
audited. An event one may not see answers like an unknown id."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.actor import Actor
from app.core.principal import Principal, SystemRole
from app.modules.audit.models import ADMIN_ACCESS, AuditLog
from app.modules.calendars.event_models import EventVisibility
from app.modules.calendars.sight import Sight, of
from app.modules.spaces.repository import SpaceRepository
from tests.factories import MakeUser
from tests.factories_calendar import (
    SECRET,
    PrivateEvent,
    listed,
    logged_in,
    new_calendar,
    new_event,
    window,
)
from tests.factories_spaces import MakeSpace, personal_space_of

CONTENT = ("title", "location", "description", "uid", "organizer")


@contextmanager
def _counting(session: AsyncSession) -> Iterator[list[str]]:
    sync_conn = session.sync_session.connection()
    statements: list[str] = []

    def _count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    sa_event.listen(sync_conn, "before_cursor_execute", _count)
    try:
        yield statements
    finally:
        sa_event.remove(sync_conn, "before_cursor_execute", _count)


def _shape(body: dict[str, Any]) -> dict[str, Any]:
    error = dict(body["error"])
    error.pop("trace_id")
    return error


async def _private_seen_through(path: str, client: AsyncClient, case: PrivateEvent) -> str:
    """What `client` gets of the private event over `path`, as text."""
    if path == "list":
        return str(await window(client, case.start, case.end))
    if path == "get":
        r = await client.get(f"/api/events/{case.event['id']}")
        assert r.status_code == 200, r.text
        return r.text
    assert path == "search"
    return str(await window(client, case.start, case.end, q=SECRET))


@pytest.mark.parametrize("path", ["list", "get", "search"])
async def test_a_private_event_is_only_busy_on_every_path(
    path: str, private_event: PrivateEvent
) -> None:
    case = private_event
    seen = await _private_seen_through(path, case.reader_client, case)
    assert SECRET not in seen
    full = await _private_seen_through(path, case.organiser_client, case)
    assert f"{SECRET}-Titel" in full
    if path == "list":
        items = await window(case.reader_client, case.start, case.end)
        assert len(items) == 4
        for item in items:
            assert item["redacted"] is True
            assert (item["title"], item["location"]) == (None, None)
            assert item["busy"] is True
        assert all(
            not i["redacted"] for i in await window(case.organiser_client, case.start, case.end)
        )
    elif path == "get":
        body = (await case.reader_client.get(f"/api/events/{case.event['id']}")).json()
        assert body["redacted"] is True
        assert {k: body[k] for k in CONTENT} == dict.fromkeys(CONTENT)
        assert (body["starts_at"], body["rrule"]) == (
            case.event["starts_at"],
            "FREQ=WEEKLY;COUNT=4",
        )
    else:
        assert await window(case.reader_client, case.start, case.end, q="Titel") == []
        assert len(await window(case.organiser_client, case.start, case.end, q="geheim-t")) == 4
    # The outsider sees nothing on any path.
    assert await window(case.outsider_client, case.start, case.end) == []
    r = await case.outsider_client.get(f"/api/events/{case.event['id']}")
    assert (r.status_code, r.json()["error"]["code"]) == (404, "event.not_found")


async def test_an_admins_window_holds_no_event_of_a_space_they_are_not_in(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    member = await make_user()
    team = await make_space("team", members=[(member, "moderator")])
    open_ = await make_space("open", members=[(member, "moderator")])
    client = await logged_in(make_client, member)
    personal = next(c for c in await listed(client) if c["is_default"])
    in_team = await new_event(client, (await new_calendar(client, team.id))["id"])
    in_personal = await new_event(client, personal["id"])
    in_open = await new_event(client, (await new_calendar(client, open_.id))["id"])
    for role in (SystemRole.OWNER, SystemRole.ADMIN):
        admin = await logged_in(make_client, await make_user(role))
        ids = {
            o["event_id"]
            for o in await window(admin, "2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z")
        }
        assert in_team["id"] not in ids and in_personal["id"] not in ids, role
        assert in_open["id"] in ids, role  # open spaces are read by role, not admin power
        found = await window(admin, "2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z", q="Termin")
        assert {o["event_id"] for o in found} == {in_open["id"]}
    entries = (await session.scalars(select(AuditLog).where(AuditLog.action == ADMIN_ACCESS))).all()
    assert entries == []


async def test_an_admin_reads_a_foreign_personal_calendar_only_by_naming_the_space_and_it_is_audited(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    member, owner = await make_user(), await make_user(SystemRole.OWNER)
    team = await make_space("team", members=[(member, "moderator")])
    client = await logged_in(make_client, member)
    personal = next(c for c in await listed(client) if c["is_default"])
    secret = await new_event(client, personal["id"], title="Arzt", visibility="private")
    in_team = await new_event(
        client, (await new_calendar(client, team.id))["id"], title="Team", visibility="private"
    )
    own_space = await personal_space_of(session, member)
    admin = await logged_in(make_client, owner)
    named = await window(
        admin, "2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z", space_id=str(own_space.id)
    )
    assert [(o["event_id"], o["title"], o["redacted"]) for o in named] == [
        (secret["id"], "Arzt", False)
    ]
    r = await admin.get(f"/api/events/{in_team['id']}")
    assert (r.status_code, r.json()["title"], r.json()["redacted"]) == (200, "Team", False)
    entries = (await session.scalars(select(AuditLog).where(AuditLog.action == ADMIN_ACCESS))).all()
    assert sorted((e.target_id, e.details["kind"]) for e in entries) == sorted(
        [(team.id, "team"), (own_space.id, "personal")]
    )
    outsider = await logged_in(make_client, await make_user())
    r = await outsider.get(
        "/api/calendar/events",
        params={
            "from": "2026-11-01T00:00:00Z",
            "to": "2026-12-01T00:00:00Z",
            "space_id": str(team.id),
        },
    )
    assert (r.status_code, r.json()["error"]["code"]) == (404, "space.not_found")


async def test_an_admin_member_sees_private_content_only_on_the_named_way(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    author, admin_user = await make_user(), await make_user(SystemRole.ADMIN)
    team = await make_space("team", members=[(author, "moderator"), (admin_user, "viewer")])
    client = await logged_in(make_client, author)
    made = await new_event(
        client, (await new_calendar(client, team.id))["id"], title="Kur", visibility="private"
    )
    admin = await logged_in(make_client, admin_user)
    span = ("2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z")
    assert [o["redacted"] for o in await window(admin, *span)] == [True]  # a list: busy
    assert [o["title"] for o in await window(admin, *span, space_id=str(team.id))] == ["Kur"]
    assert (await admin.get(f"/api/events/{made['id']}")).json()["title"] == "Kur"


async def test_an_unseen_event_answers_like_an_unknown_id(
    session: AsyncSession, make_client: Any, private_event: PrivateEvent, make_user: MakeUser
) -> None:
    case = private_event
    plain = await new_event(case.organiser_client, case.calendar["id"], title="Offen")
    for client in (case.outsider_client, await logged_in(make_client, await make_user("guest"))):
        for seen in (case.event["id"], plain["id"]):
            answers = []
            for event_id in (seen, str(uuid7())):
                with _counting(session) as statements:
                    r = await client.get(f"/api/events/{event_id}")
                answers.append((r.status_code, _shape(r.json()), len(statements)))
            assert answers[0] == answers[1]
            assert answers[0][:2] == (
                404,
                {"code": "event.not_found", "message": "event.not_found"},
            )


async def test_the_organiser_keeps_seeing_her_event_after_leaving_the_space(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    moderator, author = await make_user(), await make_user()
    team = await make_space("team", members=[(moderator, "moderator"), (author, "editor")])
    mod = await logged_in(make_client, moderator)
    calendar = await new_calendar(mod, team.id)
    others = await new_event(mod, calendar["id"], title="Fremd")
    client = await logged_in(make_client, author)
    mine = await new_event(client, calendar["id"], title="Meins", visibility="private")
    assert await SpaceRepository(session).remove_member(team.id, Principal.user(author.id))
    span = ("2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z")
    assert [(o["event_id"], o["title"]) for o in await window(client, *span)] == [
        (mine["id"], "Meins")
    ]
    assert (await client.get(f"/api/events/{mine['id']}")).json()["title"] == "Meins"
    assert (await client.get(f"/api/events/{others['id']}")).status_code == 404
    calendars = await client.get(f"/api/spaces/{team.id}/calendars")
    assert calendars.status_code == 404  # the event, never the calendar


async def test_an_archived_calendars_events_are_gone(private_event: PrivateEvent) -> None:
    case = private_event
    url = f"/api/calendars/{case.calendar['id']}"
    assert (await case.organiser_client.delete(url, params={"version": 1})).status_code == 204
    for client in (case.organiser_client, case.reader_client):
        assert await window(client, case.start, case.end) == []
        r = await client.get(f"/api/events/{case.event['id']}")
        assert (r.status_code, r.json()["error"]["code"]) == (404, "event.not_found")


@dataclass
class _Event:
    visibility: EventVisibility


def test_the_one_rule_of_sight() -> None:
    org = uuid.uuid4()
    person = Actor(org, Principal.user(uuid.uuid4()), SystemRole.MEMBER, frozenset())
    admin = Actor(org, Principal.user(uuid.uuid4()), SystemRole.ADMIN, frozenset())
    plain, private = _Event(EventVisibility.DEFAULT), _Event(EventVisibility.PRIVATE)
    cases = [
        # (actor, event, reads, attends, named) -> sight
        (person, plain, True, False, False, Sight.FULL),
        (person, private, True, False, False, Sight.BUSY),
        (person, private, True, False, True, Sight.BUSY),  # naming adds no power
        (person, plain, False, False, False, Sight.NONE),
        (person, private, False, True, False, Sight.FULL),  # the organiser
        (person, plain, False, True, False, Sight.FULL),
        (admin, private, True, False, False, Sight.BUSY),  # a list: busy, even for admins
        (admin, private, True, False, True, Sight.FULL),  # the named way (E4)
        (admin, plain, False, False, False, Sight.NONE),
    ]
    for actor, ev, reads, attends, named, expected in cases:
        got = of(actor, ev, reads=reads, attends=attends, named=named)  # type: ignore[arg-type]
        assert got == expected, (actor.system_role, ev, reads, attends, named)
