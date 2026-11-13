"""My board (plan M4b task 2, decision 4): every ticket assigned to me in every space
where I may read tickets, in a column per status category (open, active, review, done);
done only if it was finished in the last 14 days, cancelled never. Each column has its
count and first page; more per category with a cursor. A card names its space and its
status. A move to a column sets the first status of that category in the ticket's
own space (422 `ticket.category_empty` where the space has none). A fixed number of
queries per call."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.modules.spaces.repository import SpaceRepository
from app.modules.tickets.models import TicketStatus, WorkItem
from tests.factories import login
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket, patch, status_of, statuses
from tests.real_db import MakeRealClient, RealDb
from tests.test_ticket_views import _counting

CATEGORIES = ["open", "active", "review", "done"]


def _me(desk: Desk, name: str) -> dict[str, str]:
    return {"type": "user", "id": desk.id_of(name)}


async def _board(client: AsyncClient, **params: Any) -> dict[str, Any]:
    r = await client.get("/api/tickets/my-board", params=params)
    assert r.status_code == 200, r.text
    board: dict[str, Any] = r.json()
    return board


def _columns(board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["category"]: c for c in board["columns"]}


async def _finished_days_ago(session: AsyncSession, ticket: dict[str, Any], days: int) -> None:
    moment = datetime.now(UTC) - timedelta(days=days)
    await session.execute(
        update(WorkItem).where(WorkItem.id == ticket["id"]).values(status_changed_at=moment)
    )


async def test_my_tickets_of_every_space_by_category(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    other = await make_space("team", "Anders", members=[(desk.users["editor"], "editor")])
    me = _me(desk, "editor")
    open_ = await new_ticket(desk.editor, desk.space_id, "Offen", assignee=me)
    review = await status_of(desk.viewer, desk.space_id, "review")
    in_review = await new_ticket(
        desk.editor, desk.space_id, "Prüfung", assignee=me, status_id=review["id"]
    )
    elsewhere = await new_ticket(desk.editor, other.id, "Anderswo", assignee=me, priority="high")
    done = await status_of(desk.viewer, desk.space_id, "done")
    recent = await new_ticket(desk.editor, desk.space_id, "Neu fertig", assignee=me)
    recent = (await patch(desk.editor, recent, status_id=done["id"])).json()
    old = await new_ticket(desk.editor, desk.space_id, "Alt fertig", assignee=me)
    await patch(desk.editor, old, status_id=done["id"])
    await _finished_days_ago(session, old, 15)
    cancelled = await status_of(desk.viewer, desk.space_id, "cancelled")
    await new_ticket(desk.editor, desk.space_id, "Weg", assignee=me, status_id=cancelled["id"])
    await new_ticket(desk.moderator, desk.space_id, "Fremd", assignee=_me(desk, "editor2"))
    await new_ticket(desk.editor, desk.space_id, "Niemand")

    board = await _board(desk.editor)
    assert [c["category"] for c in board["columns"]] == CATEGORIES
    columns = _columns(board)
    assert {k: c["count"] for k, c in columns.items()} == {
        "open": 2,
        "active": 0,
        "review": 1,
        "done": 1,
    }
    assert [t["id"] for t in columns["open"]["items"]] == [elsewhere["id"], open_["id"]]
    assert [t["id"] for t in columns["review"]["items"]] == [in_review["id"]]
    assert [t["id"] for t in columns["done"]["items"]] == [recent["id"]]
    card = columns["open"]["items"][0]
    assert (card["space_id"], card["space_name"]) == (str(other.id), "Anders")
    assert card["status"]["category"] == "open" and "status_changed_at" in card
    assert all(c["next_cursor"] is None for c in board["columns"])


async def test_a_column_pages_on_in_board_order(desk: Desk) -> None:
    me = _me(desk, "editor")
    made = [
        await new_ticket(desk.editor, desk.space_id, f"T{i}", assignee=me, priority=p)
        for i, p in enumerate(("low", "urgent", "normal", "high", "normal"))
    ]
    board = await _board(desk.editor, limit=2)
    first = _columns(board)["open"]
    assert first["count"] == 5 and len(first["items"]) == 2
    seen = [t["id"] for t in first["items"]]
    cursor = first["next_cursor"]
    while cursor:
        r = await desk.editor.get(
            "/api/tickets/my-board/open", params={"cursor": cursor, "limit": 2}
        )
        assert r.status_code == 200, r.text
        seen += [t["id"] for t in r.json()["items"]]
        assert all("space_name" in t for t in r.json()["items"])
        cursor = r.json()["next_cursor"]
    order = [made[1], made[3], made[2], made[4], made[0]]  # priority, then number
    assert seen == [t["id"] for t in order]
    r = await desk.editor.get("/api/tickets/my-board/cancelled")
    assert r.status_code == 422


async def test_my_board_forgets_a_space_i_leave(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    """Review focus 1 (mutation probe: without the ticket scope in the board's query, the
    count after leaving stays 2 and the card stays)."""
    other = await make_space("team", "Anders", members=[(desk.users["editor"], "editor")])
    me = _me(desk, "editor")
    await new_ticket(desk.editor, desk.space_id, "Hier", assignee=me)
    gone = await new_ticket(desk.editor, other.id, "Dort", assignee=me)
    assert _columns(await _board(desk.editor))["open"]["count"] == 2
    await SpaceRepository(session).remove_member(other.id, Principal.user(desk.users["editor"].id))
    open_ = _columns(await _board(desk.editor))["open"]
    assert open_["count"] == 1 and gone["id"] not in {t["id"] for t in open_["items"]}
    r = await desk.editor.get("/api/tickets/my-board/open")
    assert gone["id"] not in r.text


async def test_my_board_takes_a_fixed_number_of_queries(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    me = _me(desk, "editor")
    tag = (await desk.admin.post("/api/tags", json={"name": "Q"})).json()

    async def calls() -> int:
        with _counting(session) as statements:
            await _board(desk.editor)
        return len(statements)

    await new_ticket(desk.editor, desk.space_id, "Eins", assignee=me)
    few = await calls()
    for i in range(3):
        space = await make_space("team", f"S{i}", members=[(desk.users["editor"], "editor")])
        for status in await statuses(desk.editor, space.id):
            ticket = await new_ticket(
                desk.editor, space.id, "T", assignee=me, status_id=status["id"]
            )
            await desk.editor.put(
                f"/api/tickets/{ticket['number']}/tags",
                json={"tag_ids": [tag["id"]], "version": ticket["version"]},
            )
    assert await calls() == few


async def test_a_move_sets_the_first_status_of_the_category_in_the_tickets_space(
    desk: Desk, make_space: MakeSpace
) -> None:
    second = await desk.manager.post(
        f"/api/spaces/{desk.space_id}/ticket-statuses",
        json={"name": "Auch aktiv", "category": "active"},
    )
    assert second.status_code == 201, second.text
    active = await status_of(desk.viewer, desk.space_id, "active")
    ticket = await new_ticket(desk.editor, desk.space_id, assignee=_me(desk, "editor"))
    url = f"/api/tickets/{ticket['number']}/move-category"
    assert (
        await desk.viewer.post(url, json={"category": "active", "version": 1})
    ).status_code == 403
    hidden = await desk.outsider.post(url, json={"category": "active", "version": 1})
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "ticket.not_found")
    r = await desk.editor.post(url, json={"category": "active", "version": 1})
    assert r.status_code == 200, r.text
    moved = r.json()
    assert (moved["status"]["id"], moved["version"]) == (active["id"], 2)
    same = await desk.editor.post(url, json={"category": "active", "version": 2})
    assert same.json()["version"] == 2  # already there: nothing changes
    stale = await desk.editor.post(url, json={"category": "done", "version": 1})
    assert stale.status_code == 409
    review = await status_of(desk.viewer, desk.space_id, "review")
    removed = await desk.manager.delete(
        f"/api/ticket-statuses/{review['id']}", params={"version": review["version"]}
    )
    assert removed.status_code == 204, removed.text
    empty = await desk.editor.post(url, json={"category": "review", "version": 2})
    assert (empty.status_code, empty.json()["error"]["code"]) == (422, "ticket.category_empty")


async def test_moving_while_the_target_status_is_deleted(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    """Review focus 2 and 3: each move lands in a status of the ticket's space that
    exists, or is refused with 422; never a 500, never a ticket without its status."""
    clients = [await make_real_client() for _ in range(4)]
    for client in clients:
        await login(client, real_db.owner_email)
    space = (await clients[0].post("/api/spaces", json={"name": "T", "kind": "team"})).json()
    url = f"/api/spaces/{space['id']}/ticket-statuses"
    items = (await clients[0].get(url)).json()["items"]
    review = next(s for s in items if s["category"] == "review")
    active = next(s for s in items if s["category"] == "active")
    for round_ in range(4):
        target = (
            await clients[0].post(
                url, json={"name": f"Prüfen {round_}", "category": "review", "position": 0}
            )
        ).json()
        made = [
            (
                await clients[0].post(f"/api/spaces/{space['id']}/tickets", json={"title": "T"})
            ).json()
            for _ in range(3)
        ]
        moves = [
            c.post(
                f"/api/tickets/{t['number']}/move-category",
                json={"category": "review", "version": 1},
            )
            for c, t in zip(clients[1:], made, strict=True)
        ]
        delete = clients[0].delete(
            f"/api/ticket-statuses/{target['id']}",
            params={"version": target["version"], "replace_with": active["id"]},
        )
        answers = await asyncio.gather(delete, *moves)
        assert answers[0].status_code == 204, answers[0].text
        for answer in answers[1:]:
            assert answer.status_code == 200, answer.text
            assert answer.json()["status"]["id"] in (target["id"], review["id"])
        for ticket in made:  # the moved-in ones went on with the deleted status's tickets
            now = (await clients[0].get(f"/api/tickets/{ticket['number']}")).json()
            assert now["status"]["id"] in (review["id"], active["id"])
    async with real_db.database.session_factory() as session:
        orphans = await session.scalars(
            select(WorkItem.id).where(~WorkItem.status_id.in_(select(TicketStatus.id)))
        )
        assert list(orphans) == []
