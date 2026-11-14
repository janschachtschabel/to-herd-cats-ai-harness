"""Sprints under real commits and concurrent requests (plan M4b review focus 2): of two
sprints started at once one is active, the other refused (409, held by the unique
index, never a 500); a sprint closed while tickets move in or out keeps a tally that
matches what stayed in it and what went out, and leaves no unfinished ticket in a
closed sprint; a sprint closed while a status of its tickets is deleted (module review
M4b, finding 2) waits for the deletion or the deletion for it, never a deadlock."""

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text

from app.modules.tickets.models import Sprint, StatusCategory, TicketStatus, WorkItem
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

N = 6


async def _clients_and_space(
    real_db: RealDb, make_real_client: MakeRealClient
) -> tuple[list[AsyncClient], dict[str, Any]]:
    clients = [await make_real_client() for _ in range(N)]
    for client in clients:
        await login(client, real_db.owner_email)
    space = (await clients[0].post("/api/spaces", json={"name": "T", "kind": "team"})).json()
    return clients, space


async def _sprint(
    client: AsyncClient, space_id: str, name: str, starts_on: str = "2026-11-16"
) -> dict[str, Any]:
    r = await client.post(
        f"/api/spaces/{space_id}/sprints",
        json={"name": name, "starts_on": starts_on, "ends_on": "2027-01-29"},
    )
    assert r.status_code == 201, r.text
    sprint: dict[str, Any] = r.json()
    return sprint


async def test_two_sprints_started_at_once(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    clients, space = await _clients_and_space(real_db, make_real_client)
    for round_ in range(4):
        made = [await _sprint(clients[0], space["id"], f"S{round_}.{i}") for i in range(N)]
        answers = await asyncio.gather(
            *(
                c.post(f"/api/sprints/{s['id']}/start", json={"version": 1})
                for c, s in zip(clients, made, strict=True)
            )
        )
        codes = sorted(a.status_code for a in answers)
        assert codes == [200] + [409] * (N - 1), [a.text for a in answers]
        assert {a.json()["error"]["code"] for a in answers if a.status_code == 409} == {
            "sprint.active_exists"
        }
        winner = next(a.json() for a in answers if a.status_code == 200)
        r = await clients[0].post(
            f"/api/sprints/{winner['id']}/close",
            json={"version": winner["version"], "move_open_to": "backlog"},
        )
        assert r.status_code == 200, r.text
    async with real_db.database.session_factory() as session:
        active = await session.scalar(select(func.count()).where(Sprint.state == "active"))
        assert active == 0


async def test_closing_a_sprint_while_tickets_move_in_and_out(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    clients, space = await _clients_and_space(real_db, make_real_client)
    tickets_url = f"/api/spaces/{space['id']}/tickets"
    for round_ in range(4):
        sprint = await _sprint(clients[0], space["id"], f"Läuft {round_}")
        # each round's next sprint starts before the last round's: it is the next one
        nxt = await _sprint(clients[0], space["id"], f"Nächster {round_}", f"2026-12-2{9 - round_}")
        made = [
            (await clients[0].post(tickets_url, json={"title": f"T{i}"})).json()
            for i in range(N - 1)
        ]
        inside = made[: (N - 1) // 2]
        for ticket in inside:
            r = await clients[0].patch(
                f"/api/tickets/{ticket['number']}", json={"version": 1, "sprint_id": sprint["id"]}
            )
            assert r.status_code == 200, r.text
        started = (
            await clients[0].post(f"/api/sprints/{sprint['id']}/start", json={"version": 1})
        ).json()
        moves = []
        for client, ticket in zip(clients[1:], made, strict=False):
            if ticket in inside:  # out of the sprint
                body = {"version": 2, "sprint_id": None}
            else:  # into it
                body = {"version": 1, "sprint_id": sprint["id"]}
            moves.append(client.patch(f"/api/tickets/{ticket['number']}", json=body))
        closing = clients[0].post(
            f"/api/sprints/{sprint['id']}/close",
            json={
                "version": started["version"],
                "move_open_to": "next" if round_ % 2 else "backlog",
            },
        )
        answers = await asyncio.gather(closing, *moves)
        assert answers[0].status_code == 200, answers[0].text
        tally = answers[0].json()["tally"]
        for answer in answers[1:]:
            assert answer.status_code in (200, 409, 422), answer.text
        async with real_db.database.session_factory() as session:
            unfinished = await session.scalar(
                select(func.count())
                .select_from(WorkItem)
                .join(TicketStatus, TicketStatus.id == WorkItem.status_id)
                .where(
                    WorkItem.sprint_id == sprint["id"],
                    TicketStatus.category.not_in((StatusCategory.DONE, StatusCategory.CANCELLED)),
                )
            )
            assert unfinished == 0
            stayed = await session.scalar(
                select(func.count()).where(WorkItem.sprint_id == sprint["id"])
            )
            assert tally["planned"] == stayed + tally["carried"]
            in_next = await session.scalar(
                select(func.count()).where(WorkItem.sprint_id == nxt["id"])
            )
            assert in_next == (tally["carried"] if round_ % 2 else 0)


async def _waiting_for_locks(real_db: RealDb, count: int) -> None:
    """Until `count` backends of the test database wait for a lock (at most 10 s)."""
    async with real_db.database.session_factory() as session:
        for _ in range(500):
            waiting = await session.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                    " AND wait_event_type = 'Lock'"
                )
            )
            if waiting is not None and waiting >= count:
                return
            await session.rollback()  # the statistics are a snapshot per transaction
            await asyncio.sleep(0.02)
    raise AssertionError(f"fewer than {count} backends wait for a lock")


@pytest.mark.parametrize("first", ["close", "delete"])
async def test_closing_a_sprint_while_a_status_of_its_tickets_is_deleted(
    real_db: RealDb, make_real_client: MakeRealClient, first: str
) -> None:
    """The tickets are stored in descending id order, so the deletion's bulk update
    locks them from the largest id down, while the closing locks them from the smallest
    up. A third transaction holds the smallest until both wait: without the space's
    status lock in the closing, the two then cross when the closing came first (40P01,
    a 500 for one of them). Either way both succeed, one after the other."""
    clients, space = await _clients_and_space(real_db, make_real_client)
    statuses_url = f"/api/spaces/{space['id']}/ticket-statuses"
    items = (await clients[0].get(statuses_url)).json()["items"]
    active = next(s for s in items if s["category"] == "active")
    extra = (
        await clients[0].post(statuses_url, json={"name": "Extra", "category": "active"})
    ).json()
    sprint = await _sprint(clients[0], space["id"], "Groß")
    ids = sorted((uuid.uuid4() for _ in range(60)), reverse=True)
    async with real_db.database.session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO work_item (id, org_id, space_id, number, kind, title, description_md,"
                " status_id, priority, reporter_type, reporter_id, sprint_id, version, created_at,"
                " updated_at)"
                " SELECT t.id, s.org_id, s.id, 1000 + t.n, 'task', 'T', '', :status, 'normal',"
                " 'user', (SELECT id FROM app_user WHERE email = :email), :sprint, 1, now(), now()"
                " FROM space s, unnest(CAST(:ids AS uuid[])) WITH ORDINALITY AS t(id, n)"
                " WHERE s.id = :space ORDER BY t.n"
            ),
            {
                "status": extra["id"],
                "email": real_db.owner_email,
                "sprint": sprint["id"],
                "ids": [str(i) for i in ids],
                "space": space["id"],
            },
        )
        await session.commit()
    started = (
        await clients[0].post(f"/api/sprints/{sprint['id']}/start", json={"version": 1})
    ).json()
    async with real_db.database.session_factory() as holder:
        await holder.execute(
            text("SELECT 1 FROM work_item WHERE id = :id FOR UPDATE"), {"id": ids[-1]}
        )
        close = clients[1].post(
            f"/api/sprints/{sprint['id']}/close",
            json={"version": started["version"], "move_open_to": "backlog"},
        )
        delete = clients[2].delete(
            f"/api/ticket-statuses/{extra['id']}",
            params={"version": extra["version"], "replace_with": active["id"]},
        )
        jobs = {"close": close, "delete": delete}
        order = [first, *(name for name in jobs if name != first)]
        tasks = {}
        for waiting, name in enumerate(order, start=1):
            tasks[name] = asyncio.create_task(jobs[name])
            await _waiting_for_locks(real_db, waiting)
        await holder.commit()
    closed, deleted = await asyncio.gather(tasks["close"], tasks["delete"])
    assert (closed.status_code, deleted.status_code) == (200, 204), (closed.text, deleted.text)
    assert closed.json()["tally"] == {"planned": 60, "done": 0, "carried": 60}
    async with real_db.database.session_factory() as session:
        rows = await session.execute(
            select(WorkItem.status_id, WorkItem.sprint_id).where(WorkItem.id.in_(ids))
        )
        assert {(str(status), sprint_) for status, sprint_ in rows} == {(active["id"], None)}
