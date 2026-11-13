"""Sprints under real commits and concurrent requests (plan M4b review focus 2): of two
sprints started at once one is active, the other refused (409, held by the unique
index, never a 500); a sprint closed while tickets move in or out keeps a tally that
matches what stayed in it and what went out, and leaves no unfinished ticket in a
closed sprint."""

import asyncio
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select

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
