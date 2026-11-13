"""Ticket views (plan M4 task 5): the board of a space (its statuses in order, each with
its count and the first page of its tickets in the fixed order of decision 8, more per
column with a cursor), the epic overview with progress, and the counts for the
sidebar. Only spaces where the caller may read tickets, filtered in SQL; a constant
number of queries per call, however many tickets and statuses."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.modules.spaces.repository import SpaceRepository
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket, patch, status_of, statuses


def _me(desk: Desk, name: str) -> dict[str, str]:
    return {"type": "user", "id": desk.id_of(name)}


async def _board(client: AsyncClient, space_id: object, **params: Any) -> dict[str, Any]:
    r = await client.get(f"/api/spaces/{space_id}/board", params=params)
    assert r.status_code == 200, r.text
    board: dict[str, Any] = r.json()
    return board


async def _column(
    client: AsyncClient, space_id: object, status_id: str, **params: Any
) -> list[dict[str, Any]]:
    """A column's tickets, every page."""
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        query = {**params, **({"cursor": cursor} if cursor else {})}
        r = await client.get(f"/api/spaces/{space_id}/board/{status_id}", params=query)
        assert r.status_code == 200, r.text
        items += r.json()["items"]
        if (cursor := r.json()["next_cursor"]) is None:
            return items


async def _list_count(client: AsyncClient, **params: Any) -> int:
    count = 0
    cursor = None
    while True:
        query = {"limit": 100, **params, **({"cursor": cursor} if cursor else {})}
        r = await client.get("/api/tickets", params=query)
        assert r.status_code == 200, r.text
        count += len(r.json()["items"])
        if (cursor := r.json()["next_cursor"]) is None:
            return count


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


async def test_the_board_shows_every_status_in_order_with_count_and_first_page(
    desk: Desk,
) -> None:
    open_ = await status_of(desk.viewer, desk.space_id, "open")
    low = await new_ticket(desk.editor, desk.space_id, "low", priority="low")
    late = await new_ticket(
        desk.editor, desk.space_id, "late", priority="high", due_on="2027-03-01"
    )
    undated = await new_ticket(desk.editor, desk.space_id, "undated", priority="high")
    soon = await new_ticket(
        desk.editor, desk.space_id, "soon", priority="high", due_on="2027-01-01"
    )
    urgent = await new_ticket(desk.editor, desk.space_id, "urgent", priority="urgent")
    tie = await new_ticket(desk.editor, desk.space_id, "tie", priority="high", due_on="2027-01-01")
    done = await status_of(desk.viewer, desk.space_id, "done")
    finished = await new_ticket(desk.editor, desk.space_id, "finished", status_id=done["id"])

    board = await _board(desk.viewer, desk.space_id, limit=3)
    names = [s["name"] for s in await statuses(desk.viewer, desk.space_id)]
    assert [c["status"]["name"] for c in board["columns"]] == names
    first = board["columns"][0]
    assert first["status"] == {"id": open_["id"], "name": "Neu", "category": "open"}
    assert first["count"] == 6
    order = [urgent, soon, tie, late, undated, low]  # priority, due (none last), number
    assert [t["id"] for t in first["items"]] == [t["id"] for t in order[:3]]
    assert first["next_cursor"] is not None
    rest = await _column(desk.viewer, desk.space_id, open_["id"], limit=2)
    assert [t["id"] for t in rest] == [t["id"] for t in order]
    by_name = {c["status"]["name"]: c for c in board["columns"]}
    assert [t["id"] for t in by_name["Erledigt"]["items"]] == [finished["id"]]
    assert by_name["Erledigt"]["next_cursor"] is None
    assert by_name["In Arbeit"] == {
        "status": by_name["In Arbeit"]["status"],
        "count": 0,
        "items": [],
        "next_cursor": None,
    }
    bad = await desk.viewer.get(
        f"/api/spaces/{desk.space_id}/board/{open_['id']}", params={"cursor": "x"}
    )
    assert bad.status_code == 422


async def test_board_counts_match_the_list_under_every_filter(desk: Desk) -> None:
    tag = (await desk.admin.post("/api/tags", json={"name": "Board"})).json()
    epic = await new_ticket(desk.editor, desk.space_id, "Epos", kind="epic")
    story = await new_ticket(
        desk.editor, desk.space_id, "Story", kind="story", parent_id=epic["id"]
    )
    deep = await new_ticket(desk.editor, desk.space_id, "Tief", kind="bug", parent_id=story["id"])
    mine = await new_ticket(desk.editor, desk.space_id, "Meins", assignee=_me(desk, "editor"))
    active = await status_of(desk.viewer, desk.space_id, "active")
    mine = (await patch(desk.editor, mine, status_id=active["id"])).json()
    r = await desk.editor.put(
        f"/api/tickets/{deep['number']}/tags", json={"tag_ids": [tag["id"]], "version": 1}
    )
    assert r.status_code == 200, r.text
    await new_ticket(desk.editor, desk.space_id, "Sonst")
    filters: list[dict[str, Any]] = [
        {},
        {"assignee": "me"},
        {"kind": "bug"},
        {"tag": tag["id"]},
    ]
    for query in filters:
        board = await _board(desk.editor, desk.space_id, **query)
        for column in board["columns"]:
            expected = await _list_count(
                desk.editor, space_id=desk.space_id, status_id=column["status"]["id"], **query
            )
            assert column["count"] == expected, (query, column["status"]["name"])
    under_epic = await _board(desk.editor, desk.space_id, epic=epic["id"])
    ids = {t["id"] for c in under_epic["columns"] for t in c["items"]}
    assert ids == {story["id"], deep["id"]}  # children and grandchildren
    assert sum(c["count"] for c in under_epic["columns"]) == 2


async def test_the_board_of_a_hidden_space_does_not_exist(
    desk: Desk, make_space: MakeSpace
) -> None:
    """(Mutation probe: without the space check, the outsider gets a board.)"""
    open_ = await status_of(desk.viewer, desk.space_id, "open")
    await new_ticket(desk.editor, desk.space_id, "Geheim")
    for path in ("/board", f"/board/{open_['id']}", "/epics"):
        r = await desk.outsider.get(f"/api/spaces/{desk.space_id}{path}")
        assert r.status_code == 404, path
        assert r.json()["error"]["code"] == "space.not_found"
    other = await make_space("team", "Anders", members=[(desk.users["viewer"], "viewer")])
    r = await desk.viewer.get(f"/api/spaces/{other.id}/board/{open_['id']}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ticket_status.not_found"


async def test_an_epic_filter_of_another_space_finds_nothing(
    desk: Desk, make_space: MakeSpace
) -> None:
    other = await make_space("team", "Anders", members=[(desk.users["editor"], "editor")])
    foreign = await new_ticket(desk.editor, other.id, "Fremd", kind="epic")
    await new_ticket(desk.editor, other.id, "Kind", kind="story", parent_id=foreign["id"])
    board = await _board(desk.editor, desk.space_id, epic=foreign["id"])
    assert all(c["count"] == 0 and c["items"] == [] for c in board["columns"])


async def test_board_and_epics_take_a_fixed_number_of_queries(
    desk: Desk, session: AsyncSession
) -> None:
    tag = (await desk.admin.post("/api/tags", json={"name": "Q"})).json()

    async def calls() -> tuple[int, int]:
        with _counting(session) as board:
            await _board(desk.viewer, desk.space_id)
        with _counting(session) as epics:
            r = await desk.viewer.get(f"/api/spaces/{desk.space_id}/epics")
            assert r.status_code == 200
        return len(board), len(epics)

    epic = await new_ticket(desk.editor, desk.space_id, "E0", kind="epic")
    await new_ticket(desk.editor, desk.space_id, "S0", kind="story", parent_id=epic["id"])
    few = await calls()
    assert min(few) > 0
    for status in await statuses(desk.viewer, desk.space_id):
        for i in range(3):
            ticket = await new_ticket(desk.editor, desk.space_id, f"T{i}", status_id=status["id"])
            await desk.editor.put(
                f"/api/tickets/{ticket['number']}/tags",
                json={"tag_ids": [tag["id"]], "version": ticket["version"]},
            )
        more = await new_ticket(desk.editor, desk.space_id, "E", kind="epic")
        await new_ticket(desk.editor, desk.space_id, "K", kind="task", parent_id=more["id"])
    assert await calls() == few


async def test_the_epic_overview_shows_progress(desk: Desk, make_space: MakeSpace) -> None:
    done = await status_of(desk.viewer, desk.space_id, "done")
    active = await status_of(desk.viewer, desk.space_id, "active")
    epics = [
        await new_ticket(desk.editor, desk.space_id, f"Epos {i}", kind="epic") for i in range(3)
    ]
    await new_ticket(desk.editor, desk.space_id, "Keine Epic")
    for status_id in (done["id"], done["id"], active["id"], None):
        fields = {"status_id": status_id} if status_id else {}
        await new_ticket(
            desk.editor, desk.space_id, "Kind", kind="story", parent_id=epics[0]["id"], **fields
        )
    other = await make_space("team", "Anders", members=[(desk.users["viewer"], "viewer")])
    await new_ticket(desk.admin, other.id, "Fremdes Epos", kind="epic")
    seen: list[dict[str, Any]] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        r = await desk.viewer.get(f"/api/spaces/{desk.space_id}/epics", params=params)
        assert r.status_code == 200, r.text
        seen += r.json()["items"]
        if (cursor := r.json()["next_cursor"]) is None:
            break
    assert [e["id"] for e in seen] == [e["id"] for e in reversed(epics)]  # newest first
    progress = {e["id"]: e["children"] for e in seen}
    assert progress[epics[0]["id"]] == {
        "open": 1,
        "active": 1,
        "review": 0,
        "done": 2,
        "cancelled": 0,
    }
    assert progress[epics[1]["id"]] == dict.fromkeys(
        ("open", "active", "review", "done", "cancelled"), 0
    )
    assert seen[0]["key"] == epics[2]["key"] and "tags" in seen[0]


async def test_counts_give_my_open_tickets_in_spaces_i_still_see(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    """(Mutation probe: without the ticket scope, the count after leaving stays 3.)"""
    other = await make_space("team", "Anders", members=[(desk.users["editor"], "editor")])
    me = _me(desk, "editor")
    await new_ticket(desk.editor, desk.space_id, "Offen", assignee=me)
    review = await status_of(desk.viewer, desk.space_id, "review")
    await new_ticket(desk.editor, desk.space_id, "Prüfung", assignee=me, status_id=review["id"])
    done = await status_of(desk.viewer, desk.space_id, "done")
    await new_ticket(desk.editor, desk.space_id, "Fertig", assignee=me, status_id=done["id"])
    await new_ticket(desk.moderator, desk.space_id, "Fremd", assignee=_me(desk, "editor2"))
    await new_ticket(desk.editor, desk.space_id, "Niemand")
    await new_ticket(desk.editor, other.id, "Anderswo", assignee=me)
    r = await desk.editor.get("/api/tickets/counts")
    assert r.status_code == 200, r.text
    assert r.json() == {"assigned_open": 3}
    expected = await _list_count(
        desk.editor, assignee="me", status_category=["open", "active", "review"]
    )
    assert expected == 3
    assert (await desk.editor2.get("/api/tickets/counts")).json() == {"assigned_open": 1}
    await SpaceRepository(session).remove_member(other.id, Principal.user(desk.users["editor"].id))
    assert (await desk.editor.get("/api/tickets/counts")).json() == {"assigned_open": 2}
