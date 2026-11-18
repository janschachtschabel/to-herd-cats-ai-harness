"""Calendars per space (plan M10 task 1, decisions 2 and 3): made, renamed and archived
by moderators of the space, listed for whoever reads it. `/api/calendars` holds the
calendars of the spaces the person is in (or open spaces she reads), the same for
admins (C1): a foreign personal or team space's calendars an admin reaches only by
naming the space, which is audited. A calendar one may not see answers like an unknown
id. Defaults: „Mein Kalender“ in the personal space and one in „Allgemein“, made once
on the first call, without a stored name (the interface words them)."""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from httpx import AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.pagination import PageParams
from app.core.principal import SystemRole
from app.modules.audit.models import ADMIN_ACCESS, AuditLog
from app.modules.calendars.models import Calendar
from app.modules.calendars.service import CalendarService, NewCalendar
from app.modules.spaces.service import GENERAL_SPACE_NAME
from app.modules.users.models import User
from tests.factories import MakeUser, login
from tests.factories_calendar import actor_of, listed, new_calendar
from tests.factories_spaces import MakeSpace, personal_space_of
from tests.real_db import MakeRealClient, RealDb


@contextmanager
def _counting(session: AsyncSession) -> Iterator[list[str]]:
    sync_conn = session.sync_session.connection()
    statements: list[str] = []

    def _count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(sync_conn, "before_cursor_execute", _count)
    try:
        yield statements
    finally:
        event.remove(sync_conn, "before_cursor_execute", _count)


async def _client(make_client: Any, user: User) -> AsyncClient:
    client: AsyncClient = await make_client(csrf=True)
    await login(client, user.email)
    return client


def _shape(body: dict[str, Any]) -> dict[str, Any]:
    error = dict(body["error"])
    error.pop("trace_id")
    return error


async def test_moderators_make_rename_and_archive_calendars_readers_list_them(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    moderator, editor, viewer = [await make_user() for _ in range(3)]
    team = await make_space(
        "team", members=[(moderator, "moderator"), (editor, "editor"), (viewer, "viewer")]
    )
    mod, ed, view = [await _client(make_client, u) for u in (moderator, editor, viewer)]
    for client in (ed, view):
        r = await client.post(f"/api/spaces/{team.id}/calendars", json={"name": "X"})
        assert (r.status_code, r.json()["error"]["code"]) == (403, "auth.permission_denied")
    made = await new_calendar(mod, team.id, "Urlaub", color="green")
    assert {k: made[k] for k in ("space_id", "name", "color", "is_default", "version")} == {
        "space_id": str(team.id),
        "name": "Urlaub",
        "color": "green",
        "is_default": False,
        "version": 1,
    }
    assert [c["id"] for c in await listed(view, f"/api/spaces/{team.id}/calendars")] == [made["id"]]
    assert made["id"] in {c["id"] for c in await listed(view)}
    url = f"/api/calendars/{made['id']}"
    r = await ed.patch(url, json={"name": "Nein", "version": 1})
    assert (r.status_code, r.json()["error"]["code"]) == (403, "auth.permission_denied")
    r = await mod.patch(url, json={"name": "Ferien", "color": "red", "version": 1})
    assert r.status_code == 200, r.text
    assert (r.json()["name"], r.json()["color"], r.json()["version"]) == ("Ferien", "red", 2)
    assert (await ed.delete(url, params={"version": 2})).status_code == 403
    assert (await mod.delete(url, params={"version": 2})).status_code == 204
    assert made["id"] not in {c["id"] for c in await listed(view)}
    assert await listed(view, f"/api/spaces/{team.id}/calendars") == []
    gone = await mod.patch(url, json={"name": "Wieder", "version": 3})
    assert (gone.status_code, gone.json()["error"]["code"]) == (404, "calendar.not_found")
    for body in (
        {"name": ""},
        {"name": " "},
        {"name": "x" * 121},
        {"name": "X", "color": "plaid"},
        {"name": "X", "is_default": True},
    ):
        r = await mod.post(f"/api/spaces/{team.id}/calendars", json=body)
        assert r.status_code == 422, body


async def test_a_team_calendar_answers_like_an_unknown_id_for_outsiders(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    moderator, outsider = await make_user(), await make_user()
    team = await make_space("team", members=[(moderator, "moderator")])
    calendar = await new_calendar(await _client(make_client, moderator), team.id)
    client = await _client(make_client, outsider)
    for method, extra in (("PATCH", {"json": {"name": "X", "version": 1}}), ("DELETE", {})):
        answers = []
        for calendar_id in (calendar["id"], str(uuid7())):
            kwargs: dict[str, Any] = {"params": {"version": 1}, **extra}
            with _counting(session) as statements:
                r = await client.request(method, f"/api/calendars/{calendar_id}", **kwargs)
            answers.append((r.status_code, _shape(r.json()), len(statements)))
        assert answers[0] == answers[1], (method, answers)
        assert answers[0][:2] == (
            404,
            {"code": "calendar.not_found", "message": "calendar.not_found"},
        )


async def test_the_list_filters_spaces_in_sql(
    session: AsyncSession, make_user: MakeUser, make_space: MakeSpace
) -> None:
    person, other = await make_user(), await make_user()
    mine = await make_space("team", members=[(person, "moderator"), (other, "moderator")])
    foreign = await make_space("team", members=[(other, "moderator")])
    service = CalendarService(session)
    other_actor, actor = await actor_of(session, other), await actor_of(session, person)
    for space in (mine, foreign, await personal_space_of(session, other)):
        await service.create(other_actor, space.id, NewCalendar(f"In {space.name}"))
    await service.list(actor, PageParams())  # makes her default calendar
    session.expunge_all()
    with _counting(session) as statements:
        page = await service.list(actor, PageParams())
    own = await personal_space_of(session, person)
    assert {c.space_id for c in page.items} == {mine.id, own.id}
    reads = [s for s in statements if "FROM calendar" in s]
    assert len(reads) == 2, statements  # the default probe and the page, nothing else
    assert "space_member" in reads[-1]  # the page filters by membership in SQL
    loaded = {obj.space_id for obj in session.identity_map.values() if isinstance(obj, Calendar)}
    assert loaded == {mine.id, own.id}  # no row of a foreign space was loaded


async def test_an_admins_list_holds_no_calendar_of_a_space_they_are_not_in(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    member = await make_user()
    team = await make_space("team", members=[(member, "moderator")])
    member_client = await _client(make_client, member)
    foreign_team = await new_calendar(member_client, team.id, "Team")
    foreign_personal = [c for c in await listed(member_client) if c["is_default"]]
    assert [c["name"] for c in foreign_personal] == [None]  # „Mein Kalender“, worded by the UI
    open_ = await make_space("open", members=[(member, "moderator")])
    shared = await new_calendar(member_client, open_.id, "Offen")
    for role in (SystemRole.OWNER, SystemRole.ADMIN):
        admin = await make_user(role)
        client = await _client(make_client, admin)
        ids = {c["id"] for c in await listed(client)}
        assert foreign_team["id"] not in ids, role
        assert foreign_personal[0]["id"] not in ids, role
        own = await personal_space_of(session, admin)
        assert {c["space_id"] for c in await listed(client)} == {str(own.id), str(open_.id)}
        assert shared["id"] in ids, role  # open spaces are read by role, not admin power
    entries = await session.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == ADMIN_ACCESS)
    )
    assert entries == 0


async def test_an_admin_lists_a_foreign_spaces_calendars_by_naming_it_and_it_is_audited(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    member, owner = await make_user(), await make_user(SystemRole.OWNER)
    team = await make_space("team", members=[(member, "moderator")])
    member_client = await _client(make_client, member)
    in_team = await new_calendar(member_client, team.id, "Team")
    personal = next(c for c in await listed(member_client) if c["is_default"])
    client = await _client(make_client, owner)
    own_space = await personal_space_of(session, member)
    for space_id, expected in ((team.id, in_team), (own_space.id, personal)):
        found = await listed(client, f"/api/spaces/{space_id}/calendars")
        assert [c["id"] for c in found] == [expected["id"]]
    entries = (await session.scalars(select(AuditLog).where(AuditLog.action == ADMIN_ACCESS))).all()
    assert sorted((e.target_id, e.details["kind"]) for e in entries) == sorted(
        [(team.id, "team"), (own_space.id, "personal")]
    )
    outsider = await _client(make_client, await make_user())
    r = await outsider.get(f"/api/spaces/{team.id}/calendars")
    assert (r.status_code, r.json()["error"]["code"]) == (404, "space.not_found")


async def test_the_personal_and_the_general_default_calendars(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    member, guest = await make_user(), await make_user(SystemRole.GUEST)
    general = await make_space("open", GENERAL_SPACE_NAME)
    other_open = await make_space("open", "Handbuch")
    client = await _client(make_client, member)
    found = await listed(client)
    own = await personal_space_of(session, member)
    assert sorted((c["space_id"], c["name"], c["is_default"]) for c in found) == sorted(
        [(str(own.id), None, True), (str(general.id), None, True)]
    )
    assert await listed(client, f"/api/spaces/{other_open.id}/calendars") == []
    assert len(await listed(client)) == 2  # made once
    guest_client = await _client(make_client, guest)
    assert [(c["space_id"], c["name"]) for c in await listed(guest_client)] == [
        (str((await personal_space_of(session, guest)).id), None)
    ]
    r = await guest_client.get(f"/api/spaces/{general.id}/calendars")
    assert r.status_code == 404  # guests read open spaces only as members


async def test_the_personal_default_calendar_appears_once(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    clients = [await make_real_client() for _ in range(6)]
    for client in clients:
        await login(client, real_db.member_email)
    answers = await asyncio.gather(*(c.get("/api/calendars") for c in clients))
    assert [a.status_code for a in answers] == [200] * 6, [a.text for a in answers]
    async with real_db.database.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(Calendar))
    assert count == 1
    assert len({a.json()["items"][0]["id"] for a in answers}) == 1


async def test_more_than_twenty_calendars_are_refused(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    moderator = await make_user()
    team = await make_space("team", members=[(moderator, "moderator")])
    client = await _client(make_client, moderator)
    made = [await new_calendar(client, team.id, f"K{i}") for i in range(20)]
    r = await client.post(f"/api/spaces/{team.id}/calendars", json={"name": "Zu viel"})
    assert (r.status_code, r.json()["error"]["code"]) == (409, "calendar.limit")
    assert (
        await client.delete(f"/api/calendars/{made[0]['id']}", params={"version": 1})
    ).is_success
    await new_calendar(client, team.id, "Platz frei")  # archived ones do not count
    names = [c["name"] for c in await listed(client, f"/api/spaces/{team.id}/calendars", limit=7)]
    assert len(names) == 20 and len(set(names)) == 20  # three pages, no gap, no repeat


async def test_update_with_a_stale_version_answers_409(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    moderator = await make_user()
    team = await make_space("team", members=[(moderator, "moderator")])
    client = await _client(make_client, moderator)
    calendar = await new_calendar(client, team.id)
    url = f"/api/calendars/{calendar['id']}"
    assert (await client.patch(url, json={"name": "Neu", "version": 1})).status_code == 200
    for r in (
        await client.patch(url, json={"name": "Alt", "version": 1}),
        await client.delete(url, params={"version": 1}),
    ):
        assert (r.status_code, r.json()["error"]["code"]) == (409, "calendar.version_conflict")
        assert r.json()["error"]["details"] == {"current_version": 2}
