"""Overlays (plan M10 task 9, decision 16): ticket due dates, sprints and automation
terms shown in the calendar, read from their own tables and stored nowhere.

Tickets and sprints come from the spaces one belongs to (`access.member_space_ids`:
an admin's overlays hold only her own spaces, never what admin power opens); an
automation shows to whom `automations/sight.py` shows it, and only where it sits in
such a space or is one's own. Everything is filtered in SQL and paged by (starts_on,
kind, id), automations within a day by their term."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.core.permissions import READ_ACTIONS, SPACE_ACTION_MIN_ROLE, Action, SpaceRole
from app.core.principal import Principal
from app.modules.audit.models import ADMIN_ACCESS, AuditLog
from app.modules.automations.models import Automation
from app.modules.calendars.models import Calendar
from app.modules.calendars.overlays import OverlayKind, list_overlays
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository
from app.modules.tickets.models import Sprint, WorkItem
from tests.factories_agents import open_agent_dm
from tests.factories_automations import placed
from tests.factories_calendar import actor_of
from tests.factories_spaces import MakeSpace
from tests.factories_sprints import new_sprint
from tests.factories_tickets import new_ticket, patch, status_of
from tests.factories_writing import Work

URL = "/api/calendar/overlays"
FROM, TO = "2026-11-16", "2026-11-30"
MAX_PAGES = 100
ALL = {OverlayKind.TICKETS, OverlayKind.SPRINTS, OverlayKind.AUTOMATIONS}


async def overlays(client: AsyncClient, limit: int = 100, **params: Any) -> list[dict[str, Any]]:
    """Every overlay of the range, page by page (a cursor that never ends fails)."""
    items: list[dict[str, Any]] = []
    cursor = None
    for _ in range(MAX_PAGES):
        query: dict[str, Any] = {"from": FROM, "to": TO, "limit": limit, **params}
        if cursor:
            query["cursor"] = cursor
        r = await client.get(URL, params=query)
        assert r.status_code == 200, r.text
        items += r.json()["items"]
        if (cursor := r.json()["next_cursor"]) is None:
            return items
    raise AssertionError("the pages do not end")


def refs(items: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {(i["kind"], i["ref"]) for i in items}


async def _channel(client: AsyncClient, space_id: object, name: str) -> uuid.UUID:
    r = await client.post(f"/api/spaces/{space_id}/channels", json={"name": name})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


@dataclass
class Scene:
    work: Work
    foreign: Space  # Carol's alone
    shown: dict[str, tuple[str, str]]  # name → (kind, ref)


def _term(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 11, day, hour, tzinfo=UTC)


async def _scene(work: Work, make_space: MakeSpace) -> Scene:
    """Werkstatt (Alice, the admin, Bob as a viewer), Geheim (Alice, the admin) and
    Carol's Fremd, each with what overlays can show, and things they never show."""
    bench, people = work.bench, work.bench.people
    carol = people.users["carol"]
    await SpaceRepository(bench.session).set_member(
        work.space.id, Principal.user(people.users["bob"].id), SpaceRole.VIEWER
    )
    foreign = await make_space(SpaceKind.TEAM, name="Fremd", members=[(carol, SpaceRole.ADMIN)])
    admin = people.admin
    shown: dict[str, tuple[str, str]] = {}

    async def ticket(name: str, client: AsyncClient, space: Space, due: str | None) -> Any:
        made = await new_ticket(client, space.id, name, due_on=due)
        shown[name] = ("tickets", made["key"])
        return made

    async def sprint(name: str, client: AsyncClient, space: Space, start: str, end: str) -> None:
        made = await new_sprint(client, space.id, name, starts_on=start, ends_on=end)
        shown[name] = ("sprints", made["id"])

    async def automation(name: str, place: object, owner: str, **fields: Any) -> None:
        made = await placed(bench, place, owner=owner, **fields)
        shown[name] = ("automations", str(made.id))

    await ticket("werk-ticket", admin, work.space, "2026-11-20")
    await ticket("werk-later", admin, work.space, "2026-12-03")  # after the range
    await ticket("werk-undated", admin, work.space, None)
    done = await ticket("werk-done", admin, work.space, "2026-11-21")
    r = await patch(admin, done, status_id=(await status_of(admin, work.space.id, "done"))["id"])
    assert r.status_code == 200, r.text
    await ticket("geheim-ticket", admin, work.private, "2026-11-18")
    await ticket("fremd-ticket", people.carol, foreign, "2026-11-19")
    await sprint("werk-sprint", admin, work.space, "2026-11-09", "2026-11-20")  # reaches in
    await sprint("werk-old", admin, work.space, "2026-10-01", "2026-10-14")  # before
    await sprint("fremd-sprint", people.carol, foreign, "2026-11-23", "2026-12-04")
    werk_channel = await _channel(admin, work.space.id, "puls")
    fremd_channel = await _channel(people.carol, foreign.id, "fremd")
    bob_dm = await open_agent_dm(people.bob, bench.agent)
    await automation("werk-auto", werk_channel, "alice", due=_term(17))
    await automation("werk-paused", werk_channel, "alice", due=_term(18), paused=True)
    await automation("alice-dm-auto", bench.dm_id, "alice", due=_term(19), cron=None)
    await automation("bob-dm-auto", bob_dm["id"], "bob", due=_term(24))
    await automation("fremd-auto", fremd_channel, "carol", due=_term(25))
    await automation("werk-later-auto", werk_channel, "alice", due=_term(30, 12))
    return Scene(work, foreign, shown)


def _expect(scene: Scene, *names: str) -> set[tuple[str, str]]:
    return {scene.shown[n] for n in names}


async def test_overlays_show_only_what_the_person_may_see(
    work: Work, make_space: MakeSpace
) -> None:
    scene = await _scene(work, make_space)
    people = work.bench.people
    werk = ("werk-ticket", "werk-sprint")
    assert refs(await overlays(people.bob)) == _expect(scene, *werk, "bob-dm-auto")
    assert refs(await overlays(people.alice)) == _expect(
        scene, *werk, "geheim-ticket", "werk-auto", "alice-dm-auto"
    )
    assert refs(await overlays(people.carol)) == _expect(
        scene, "fremd-ticket", "fremd-sprint", "fremd-auto"
    )
    assert await overlays(people.gast) == []
    item = next(i for i in await overlays(people.bob) if i["kind"] == "sprints")
    assert item == {
        "kind": "sprints",
        "id": scene.shown["werk-sprint"][1],
        "space_id": str(work.space.id),
        "starts_on": "2026-11-09",
        "ends_on": "2026-11-20",
        "ref": scene.shown["werk-sprint"][1],
        "title": "werk-sprint",
        "at": None,
    }
    (ticket,) = [i for i in await overlays(people.bob) if i["kind"] == "tickets"]
    assert (ticket["starts_on"], ticket["ends_on"], ticket["title"]) == (
        "2026-11-20",
        "2026-11-20",
        "werk-ticket",
    )
    (term,) = [i for i in await overlays(people.bob) if i["kind"] == "automations"]
    assert (term["starts_on"], term["at"], term["space_id"], term["title"]) == (
        "2026-11-24",
        "2026-11-24T09:00:00Z",
        None,  # a DM has no space
        "Ava",
    )


async def test_kinds_pick_what_shows(work: Work, make_space: MakeSpace) -> None:
    scene = await _scene(work, make_space)
    alice = work.bench.people.alice
    assert refs(await overlays(alice, kinds="sprints")) == _expect(scene, "werk-sprint")
    assert refs(await overlays(alice, kinds="tickets,automations")) == _expect(
        scene, "werk-ticket", "geheim-ticket", "werk-auto", "alice-dm-auto"
    )
    r = await alice.get(URL, params={"from": FROM, "to": TO, "kinds": "tickets,events"})
    assert (r.status_code, r.json()["error"]["code"]) == (422, "calendar.overlay_kind_unknown")


async def test_an_automation_term_lies_on_the_viewers_day(work: Work) -> None:
    bench = work.bench
    made = await placed(bench, bench.dm_id, due=datetime(2026, 11, 16, 23, 30, tzinfo=UTC))
    alice = bench.people.alice
    utc = await overlays(alice, kinds="automations")
    berlin = await overlays(alice, kinds="automations", time_zone="Europe/Berlin")
    assert [(i["id"], i["starts_on"]) for i in utc] == [(str(made.id), "2026-11-16")]
    assert [(i["id"], i["starts_on"]) for i in berlin] == [(str(made.id), "2026-11-17")]
    honolulu = await alice.get(
        URL, params={"from": "2026-11-17", "to": TO, "time_zone": "Pacific/Honolulu"}
    )
    assert honolulu.json()["items"] == []  # 13:30 on the 16th there


async def test_an_admins_overlays_hold_only_their_own_spaces(
    session: AsyncSession, work: Work, make_space: MakeSpace
) -> None:
    """The admin manages every agent (`agent.manage`) and may read every space, yet her
    overlays hold only the spaces she is in: not Carol's Fremd, not Alice's DM."""
    scene = await _scene(work, make_space)
    admin = work.bench.people.admin
    assert refs(await overlays(admin)) == _expect(
        scene, "werk-ticket", "werk-sprint", "geheim-ticket", "werk-auto"
    )
    entries = await session.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == ADMIN_ACCESS)
    )
    assert entries == 0


@contextmanager
def _statements(session: AsyncSession) -> Iterator[list[str]]:
    sync_conn = session.sync_session.connection()
    statements: list[str] = []

    def _note(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(sync_conn, "before_cursor_execute", _note)
    try:
        yield statements
    finally:
        event.remove(sync_conn, "before_cursor_execute", _note)


@contextmanager
def _loading(session: AsyncSession) -> Iterator[list[object]]:
    """Every row the session loads, held (the identity map only holds them weakly)."""
    loaded: list[object] = []

    def _keep(_session, instance) -> None:  # type: ignore[no-untyped-def]
        loaded.append(instance)

    event.listen(session.sync_session, "loaded_as_persistent", _keep)
    try:
        yield loaded
    finally:
        event.remove(session.sync_session, "loaded_as_persistent", _keep)


async def test_overlays_filter_in_sql(
    session: AsyncSession, work: Work, make_space: MakeSpace
) -> None:
    scene = await _scene(work, make_space)
    for n in range(20):  # much more out of sight than in it
        await new_ticket(work.bench.people.carol, scene.foreign.id, f"f{n}", due_on="2026-11-20")
    actor = await actor_of(session, work.bench.people.users["admin"])
    session.expunge_all()
    with _statements(session) as statements, _loading(session) as loaded:
        page = await list_overlays(
            session,
            actor,
            start=date(2026, 11, 16),
            end=date(2026, 11, 30),
            kinds=ALL,
            params=PageParams(limit=100),
        )
    assert len(page.items) == 4
    reads = {
        name: [s for s in statements if f"FROM {name}" in s]
        for name in ("work_item", "sprint", "automation")
    }
    for name, found in reads.items():
        assert len(found) == 1, (name, statements)  # one statement per kind
        assert "space_member" in found[0], name  # membership filtered in SQL
    rows = [o for o in loaded if isinstance(o, WorkItem | Sprint)]
    assert {o.space_id for o in rows} == {work.space.id, work.private.id}
    automations = [o for o in loaded if isinstance(o, Automation)]
    assert [str(a.id) for a in automations] == [scene.shown["werk-auto"][1]]


async def test_overlays_page_without_gaps(work: Work, make_space: MakeSpace) -> None:
    """Ties everywhere: tickets and sprints on one day, several automations on one day,
    in a viewer zone that moves their day; every page size gives the one list."""
    scene = await _scene(work, make_space)
    bench, admin = work.bench, work.bench.people.admin
    for n in range(4):
        await new_ticket(admin, work.space.id, f"t{n}", due_on="2026-11-20")
        await new_sprint(
            admin, work.space.id, f"s{n}", starts_on="2026-11-20", ends_on="2026-11-21"
        )
    channel = await _channel(admin, work.space.id, "takt")
    for hour in (22, 23, 23, 5):
        await placed(bench, channel, due=_term(19 if hour > 5 else 20, hour))
    alice = bench.people.alice
    zone = {"time_zone": "Europe/Berlin"}
    whole = await overlays(alice, **zone)
    keys = [(i["starts_on"], i["kind"], i["at"] or "", i["id"]) for i in whole]
    assert keys == sorted(keys) and len(set(keys)) == len(keys) == 17
    assert scene.shown["werk-auto"] in refs(whole)
    for limit in (1, 2, 3, 7):
        assert await overlays(alice, limit=limit, **zone) == whole, limit
    r = await alice.get(URL, params={"from": FROM, "to": TO, "limit": 1, **zone})
    cursor = r.json()["next_cursor"]
    again = await alice.get(URL, params={"from": FROM, "to": TO, "cursor": cursor})
    assert (again.status_code, again.json()["error"]["code"]) == (
        422,
        "calendar.cursor_time_zone",
    )
    bad = await alice.get(URL, params={"from": FROM, "to": TO, "cursor": "eyJ4Ijoi"})
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "validation_failed")


async def test_overlays_store_nothing(
    session: AsyncSession, work: Work, make_space: MakeSpace
) -> None:
    await _scene(work, make_space)
    actor = await actor_of(session, work.bench.people.users["alice"])
    calendars = await session.scalar(select(func.count()).select_from(Calendar))
    with _statements(session) as statements:
        page = await list_overlays(
            session,
            actor,
            start=date(2026, 11, 16),
            end=date(2026, 11, 30),
            kinds=ALL,
            params=PageParams(limit=2),
        )
        assert page.next_cursor is not None
        await list_overlays(
            session,
            actor,
            start=date(2026, 11, 16),
            end=date(2026, 11, 30),
            kinds=ALL,
            params=PageParams(limit=2, cursor=page.next_cursor),
        )
    assert statements
    writes = [s for s in statements if not s.lstrip().upper().startswith("SELECT")]
    assert writes == []  # no row written, no savepoint, no default calendar, no audit
    assert await session.scalar(select(func.count()).select_from(Calendar)) == calendars


async def test_a_range_is_checked(work: Work) -> None:
    alice = work.bench.people.alice
    cases = [
        ({"from": TO, "to": FROM}, "calendar.invalid_window"),
        ({"from": FROM, "to": FROM}, "calendar.invalid_window"),
        ({"from": "1899-12-31", "to": FROM}, "calendar.window_out_of_range"),
        ({"from": FROM, "to": "2400-01-02"}, "calendar.window_out_of_range"),
        ({"from": FROM, "to": TO, "time_zone": "Mars/Base"}, "calendar.invalid_time_zone"),
    ]
    for params, code in cases:
        r = await alice.get(URL, params=params)
        assert (r.status_code, r.json()["error"]["code"]) == (422, code), params
    r = await alice.get(URL, params={"from": FROM, "to": "2400-01-01", "kinds": "sprints"})
    assert r.status_code == 200, r.text


def test_every_member_space_reads_tickets() -> None:
    """Overlays take tickets and sprints from `member_space_ids` alone: that is exact
    only while reading tickets needs no more than a viewer's role."""
    assert Action.TICKET_READ in READ_ACTIONS
    assert SPACE_ACTION_MIN_ROLE[Action.TICKET_READ] == SpaceRole.VIEWER
