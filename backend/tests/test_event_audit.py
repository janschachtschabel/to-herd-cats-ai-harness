"""Admin power over private events leaves a trace (review M10 task 3a, R3a-4; Jan:
admin access is logged): every read whose full sight comes from admin power alone
(the event would be "busy" without it) writes one `calendar.private_read` entry per
admin, event and UTC day, ids only; a member admin and an open space included, by id
and through `space_id=`. A person's own rights never write one."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.audit.models import CALENDAR_PRIVATE_READ, AuditLog
from app.modules.users.models import User
from tests.factories import MakeUser
from tests.factories_calendar import PrivateEvent, logged_in, new_calendar, new_event, window
from tests.factories_spaces import MakeSpace

SPAN = ("2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z")


async def _entries(session: AsyncSession, user: User) -> list[AuditLog]:
    return list((await session.scalars(select(AuditLog).where(AuditLog.actor_id == user.id))).all())


async def test_an_admin_member_reading_a_private_event_by_id_leaves_one_entry(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    author, admin_user = await make_user(), await make_user(SystemRole.ADMIN)
    team = await make_space("team", members=[(author, "moderator"), (admin_user, "viewer")])
    client = await logged_in(make_client, author)
    calendar = await new_calendar(client, team.id)
    made = await new_event(client, calendar["id"], title="Kur", visibility="private")
    admin = await logged_in(make_client, admin_user)
    for _ in range(2):
        r = await admin.get(f"/api/events/{made['id']}")
        assert (r.status_code, r.json()["title"]) == (200, "Kur")
    [entry] = await _entries(session, admin_user)
    assert (entry.action, entry.target_type, str(entry.target_id)) == (
        CALENDAR_PRIVATE_READ,
        "calendar_event",
        made["id"],
    )
    assert entry.details == {"space_id": str(team.id), "calendar_id": calendar["id"]}


async def test_the_named_window_audits_the_private_events_it_shows_by_admin_power(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    author, admin_user = await make_user(), await make_user(SystemRole.OWNER)
    team = await make_space("team", members=[(author, "moderator"), (admin_user, "viewer")])
    client = await logged_in(make_client, author)
    calendar = await new_calendar(client, team.id)
    private = await new_event(client, calendar["id"], title="Kur", visibility="private")
    await new_event(client, calendar["id"], title="Offen")
    admin = await logged_in(make_client, admin_user)
    assert [o["redacted"] for o in await window(admin, *SPAN) if o["title"] is None] == [True]
    assert await _entries(session, admin_user) == []  # a list: busy, no admin power
    named = await window(admin, *SPAN, space_id=str(team.id))
    assert sorted(o["title"] for o in named) == ["Kur", "Offen"]
    await window(admin, *SPAN, space_id=str(team.id))
    assert [(e.action, str(e.target_id)) for e in await _entries(session, admin_user)] == [
        (CALENDAR_PRIVATE_READ, private["id"])
    ]


async def test_an_admin_in_an_open_space_leaves_an_entry_too(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    author, admin_user = await make_user(), await make_user(SystemRole.ADMIN)
    space = await make_space("open", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    made = await new_event(
        client, (await new_calendar(client, space.id))["id"], visibility="private"
    )
    r = await (await logged_in(make_client, admin_user)).get(f"/api/events/{made['id']}")
    assert r.json()["redacted"] is False
    assert [e.action for e in await _entries(session, admin_user)] == [CALENDAR_PRIVATE_READ]


async def test_ones_own_rights_never_write_an_entry(
    session: AsyncSession, make_client: Any, private_event: PrivateEvent, make_user: MakeUser
) -> None:
    case = private_event
    assert (await case.reader_client.get(f"/api/events/{case.event['id']}")).json()["redacted"]
    await window(case.reader_client, case.start, case.end, space_id=str(case.space.id))
    organised = await case.organiser_client.get(f"/api/events/{case.event['id']}")
    assert organised.json()["redacted"] is False
    plain = await new_event(case.organiser_client, case.calendar["id"], title="Offen")
    admin_user = await make_user(SystemRole.ADMIN)
    admin = await logged_in(make_client, admin_user)
    await admin.get(f"/api/events/{plain['id']}")  # not private: no admin power over content
    for user in (case.reader, case.organiser):
        assert await _entries(session, user) == []
    assert [e.action for e in await _entries(session, admin_user)] == ["space.admin_access"]
