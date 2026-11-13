"""Tickets under real commits and concurrent requests (review focus 4): numbers never
repeat, one of two writes with the same version wins, a status deleted while a ticket
moves into it leaves the ticket in a status that exists, and a kind change racing a
new child never leaves the hierarchy broken."""

import asyncio
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.modules.tickets.models import TicketStatus, WorkItem
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

N = 8


async def _owner_and_space(
    real_db: RealDb, make_real_client: MakeRealClient
) -> tuple[list[AsyncClient], dict[str, Any]]:
    clients = [await make_real_client() for _ in range(N)]
    for client in clients:
        await login(client, real_db.owner_email)
    space = (await clients[0].post("/api/spaces", json={"name": "T", "kind": "team"})).json()
    return clients, space


async def _statuses(client: AsyncClient, space_id: str) -> dict[str, dict[str, Any]]:
    items = (await client.get(f"/api/spaces/{space_id}/ticket-statuses")).json()["items"]
    return {s["category"]: s for s in items}


async def test_concurrent_creations_get_different_numbers(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    clients, space = await _owner_and_space(real_db, make_real_client)
    url = f"/api/spaces/{space['id']}/tickets"
    answers = await asyncio.gather(
        *(c.post(url, json={"title": f"T{i}"}) for i, c in enumerate(clients))
    )
    assert {a.status_code for a in answers} == {201}
    assert sorted(a.json()["number"] for a in answers) == list(range(1, N + 1))


async def test_two_writes_of_one_version_one_conflicts(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    clients, space = await _owner_and_space(real_db, make_real_client)
    statuses = await _statuses(clients[0], space["id"])
    ticket = (
        await clients[0].post(f"/api/spaces/{space['id']}/tickets", json={"title": "T"})
    ).json()
    url = f"/api/tickets/{ticket['number']}"
    answers = await asyncio.gather(
        clients[0].patch(url, json={"version": 1, "status_id": statuses["active"]["id"]}),
        clients[1].patch(url, json={"version": 1, "status_id": statuses["done"]["id"]}),
    )
    assert sorted(a.status_code for a in answers) == [200, 409]


async def test_deleting_a_status_while_tickets_move_into_it(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    clients, space = await _owner_and_space(real_db, make_real_client)
    for round_ in range(4):
        statuses = await _statuses(clients[0], space["id"])
        target = (
            await clients[0].post(
                f"/api/spaces/{space['id']}/ticket-statuses",
                json={"name": f"Ziel {round_}", "category": "active"},
            )
        ).json()
        made = [
            (
                await clients[0].post(f"/api/spaces/{space['id']}/tickets", json={"title": "T"})
            ).json()
            for _ in range(3)
        ]
        moves = [
            c.patch(f"/api/tickets/{t['number']}", json={"version": 1, "status_id": target["id"]})
            for c, t in zip(clients[1:], made, strict=False)
        ]
        delete = clients[0].delete(
            f"/api/ticket-statuses/{target['id']}",
            params={"version": target["version"], "replace_with": statuses["review"]["id"]},
        )
        answers = await asyncio.gather(delete, *moves)
        assert answers[0].status_code == 204, answers[0].text
        for answer in answers[1:]:
            assert answer.status_code in (200, 422), answer.text
            if answer.status_code == 422:
                assert answer.json()["error"]["code"] == "ticket.status_invalid"
    async with real_db.database.session_factory() as session:
        orphans = await session.scalars(
            select(WorkItem.id).where(~WorkItem.status_id.in_(select(TicketStatus.id)))
        )
        assert list(orphans) == []


async def test_a_kind_change_racing_a_new_child(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    clients, space = await _owner_and_space(real_db, make_real_client)
    url = f"/api/spaces/{space['id']}/tickets"
    for _ in range(4):
        epic = (await clients[0].post(url, json={"title": "E", "kind": "epic"})).json()
        to_story = clients[0].patch(
            f"/api/tickets/{epic['number']}", json={"version": 1, "kind": "story"}
        )
        child = clients[1].post(url, json={"title": "S", "kind": "story", "parent_id": epic["id"]})
        changed, created = await asyncio.gather(to_story, child)
        assert not (changed.status_code == 200 and created.status_code == 201), (
            changed.text,
            created.text,
        )
        assert {changed.status_code, created.status_code} <= {200, 201, 422}


async def test_two_tickets_made_each_others_parent_at_once(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    """Review M4 P2: each request holds its own ticket and asks for the other as parent;
    the locks are taken in one order, so one wins and the other is refused (422), never
    a deadlock answered with 500."""
    clients, space = await _owner_and_space(real_db, make_real_client)
    url = f"/api/spaces/{space['id']}/tickets"
    for _ in range(4):
        a = (await clients[0].post(url, json={"title": "A", "kind": "story"})).json()
        b = (await clients[1].post(url, json={"title": "B", "kind": "story"})).json()
        answers = await asyncio.gather(
            clients[0].patch(
                f"/api/tickets/{a['number']}",
                json={"version": 1, "parent_id": b["id"], "kind": "task"},
            ),
            clients[1].patch(
                f"/api/tickets/{b['number']}",
                json={"version": 1, "parent_id": a["id"], "kind": "task"},
            ),
        )
        codes = sorted(answer.status_code for answer in answers)
        assert codes == [200, 422], [answer.text for answer in answers]
        refused = next(answer for answer in answers if answer.status_code == 422)
        assert refused.json()["error"]["code"] == "ticket.parent_invalid"
        async with real_db.database.session_factory() as session:
            parents = dict(
                (
                    await session.execute(
                        select(WorkItem.id, WorkItem.parent_id).where(
                            WorkItem.id.in_([a["id"], b["id"]])
                        )
                    )
                ).all()
            )
        assert sum(parent is not None for parent in parents.values()) == 1
