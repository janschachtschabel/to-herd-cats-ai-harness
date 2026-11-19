"""The scene of the calendar overlays' tests (plan M10 task 9): Werkstatt (Alice, the
admin, Bob as a viewer), Geheim (Alice, the admin) and Carol's Fremd, each with what
overlays can show and things they never show; a reader of every page, and watchers
of the statements and rows a call sends and loads."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.calendars.overlays import OverlayKind
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository
from tests.factories_agents import open_agent_dm
from tests.factories_automations import placed
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


async def new_channel(client: AsyncClient, space_id: object, name: str) -> uuid.UUID:
    r = await client.post(f"/api/spaces/{space_id}/channels", json={"name": name})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


@dataclass
class Scene:
    work: Work
    foreign: Space  # Carol's alone
    shown: dict[str, tuple[str, str]]  # name → (kind, ref)


def term(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 11, day, hour, tzinfo=UTC)


async def set_scene(work: Work, make_space: MakeSpace) -> Scene:
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
    werk_channel = await new_channel(admin, work.space.id, "puls")
    fremd_channel = await new_channel(people.carol, foreign.id, "fremd")
    bob_dm = await open_agent_dm(people.bob, bench.agent)
    await automation("werk-auto", werk_channel, "alice", due=term(17))
    await automation("werk-paused", werk_channel, "alice", due=term(18), paused=True)
    await automation("alice-dm-auto", bench.dm_id, "alice", due=term(19), cron=None)
    await automation("bob-dm-auto", bob_dm["id"], "bob", due=term(24))
    await automation("fremd-auto", fremd_channel, "carol", due=term(25))
    await automation("werk-later-auto", werk_channel, "alice", due=term(30, 12))
    return Scene(work, foreign, shown)


def expect(scene: Scene, *names: str) -> set[tuple[str, str]]:
    return {scene.shown[n] for n in names}


@contextmanager
def sent(session: AsyncSession) -> Iterator[list[str]]:
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
def loading(session: AsyncSession) -> Iterator[list[object]]:
    """Every row the session loads, held (the identity map only holds them weakly)."""
    loaded: list[object] = []

    def _keep(_session, instance) -> None:  # type: ignore[no-untyped-def]
        loaded.append(instance)

    event.listen(session.sync_session, "loaded_as_persistent", _keep)
    try:
        yield loaded
    finally:
        event.remove(session.sync_session, "loaded_as_persistent", _keep)
