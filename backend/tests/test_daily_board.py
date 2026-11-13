"""The team board for the daily (plan M4b task 2, decisions 5 and 6): the board of a
space grouped by assignee (`group_by=assignee`): a row per person with tickets under
the filters, ordered by name, and one for the unassigned last; per status a cell with
its count, how many changed status since the last working day began, and the first
tickets, each flagged `changed`. More of a cell comes from the column
(`/board/{status_id}?assignee=<id>|none`). "Since the last working day": since 0:00
(UTC) of the latest weekday before today, Monday to Friday, so on a Monday since
Friday. Only visible tickets, a fixed number of queries."""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.models import Message
from app.modules.tickets.daily import last_working_day_start
from app.modules.tickets.models import WorkItem
from tests.factories_spaces import MakeSpace
from tests.factories_sprints import new_sprint
from tests.factories_tickets import Desk, new_ticket, patch, status_of, statuses
from tests.page_thread_helpers import messages
from tests.test_ticket_views import _counting
from tests.ticket_thread_helpers import ticket_handlers, ticket_thread


def _me(desk: Desk, name: str) -> dict[str, str]:
    return {"type": "user", "id": desk.id_of(name)}


async def _daily(client: AsyncClient, space_id: object, **params: Any) -> dict[str, Any]:
    r = await client.get(f"/api/spaces/{space_id}/board", params={"group_by": "assignee", **params})
    assert r.status_code == 200, r.text
    board: dict[str, Any] = r.json()
    return board


def _cell(row: dict[str, Any], status_id: str) -> dict[str, Any]:
    return next(c for c in row["cells"] if c["status_id"] == status_id)


async def _changed_before(session: AsyncSession, ticket: dict[str, Any], since: datetime) -> None:
    await session.execute(
        update(WorkItem)
        .where(WorkItem.id == ticket["id"])
        .values(status_changed_at=since - timedelta(minutes=1))
    )


def test_the_last_working_day_begins_yesterday_and_on_mondays_on_friday() -> None:
    def at(day: str) -> datetime:
        return datetime.fromisoformat(f"{day}T09:30:00+00:00")

    expected = {
        "2026-11-17": "2026-11-16",  # Tuesday: since Monday
        "2026-11-20": "2026-11-19",  # Friday: since Thursday
        "2026-11-16": "2026-11-13",  # Monday: since Friday
        "2026-11-21": "2026-11-20",  # Saturday: since Friday
        "2026-11-22": "2026-11-20",  # Sunday: since Friday
    }
    for today, since in expected.items():
        start = last_working_day_start(at(today))
        assert start == datetime.fromisoformat(f"{since}T00:00:00+00:00"), today
    late = datetime(2026, 11, 17, 0, 30, tzinfo=UTC)
    assert last_working_day_start(late) == datetime(2026, 11, 16, tzinfo=UTC)


async def test_a_row_per_person_and_the_unassigned_last(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    open_ = await status_of(desk.viewer, desk.space_id, "open")
    active = await status_of(desk.viewer, desk.space_id, "active")
    editor = await new_ticket(desk.moderator, desk.space_id, "E1", assignee=_me(desk, "editor"))
    busy = await new_ticket(
        desk.moderator, desk.space_id, "E2", assignee=_me(desk, "editor"), priority="urgent"
    )
    busy = (await patch(desk.editor, busy, status_id=active["id"])).json()
    viewer = await new_ticket(desk.moderator, desk.space_id, "V1", assignee=_me(desk, "viewer"))
    nobody = await new_ticket(desk.editor, desk.space_id, "N1")
    other = await make_space("team", "Anders", members=[(desk.users["editor"], "editor")])
    await new_ticket(desk.editor, other.id, "Anderswo", assignee=_me(desk, "editor"))
    board = await _daily(desk.viewer, desk.space_id)
    since = datetime.fromisoformat(board["changed_since"])
    assert since == last_working_day_start(datetime.now(UTC))
    await _changed_before(session, editor, since)
    board = await _daily(desk.viewer, desk.space_id)
    names = [r["assignee"]["name"] if r["assignee"] else None for r in board["rows"]]
    assert names == ["Desk editor", "Desk viewer", None]
    assert board["rows_truncated"] is False
    ids = [s["id"] for s in await statuses(desk.viewer, desk.space_id)]
    assert [c["status"]["id"] for c in board["columns"]] == ids
    assert [c["count"] for c in board["columns"]][:2] == [3, 1]
    assert all(c["items"] == [] for c in board["columns"])  # the tickets are in the rows
    first = board["rows"][0]
    assert [c["status_id"] for c in first["cells"]] == ids
    assert first["assignee"] == {"type": "user", "id": desk.id_of("editor"), "name": "Desk editor"}
    cell = _cell(first, open_["id"])
    assert (cell["count"], cell["changed"]) == (1, 0)
    assert [(t["id"], t["changed"]) for t in cell["items"]] == [(editor["id"], False)]
    cell = _cell(first, active["id"])
    assert (cell["count"], cell["changed"]) == (1, 1)
    assert [(t["id"], t["changed"]) for t in cell["items"]] == [(busy["id"], True)]
    assert [t["id"] for t in _cell(board["rows"][1], open_["id"])["items"]] == [viewer["id"]]
    assert [t["id"] for t in _cell(board["rows"][2], open_["id"])["items"]] == [nobody["id"]]
    assert sum(c["count"] for r in board["rows"] for c in r["cells"]) == 4


async def test_cells_page_on_through_the_column_and_match_the_list(desk: Desk) -> None:
    open_ = await status_of(desk.viewer, desk.space_id, "open")
    mine = [
        await new_ticket(desk.moderator, desk.space_id, f"M{i}", assignee=_me(desk, "editor"))
        for i in range(3)
    ]
    loose = [await new_ticket(desk.editor, desk.space_id, f"L{i}") for i in range(3)]
    board = await _daily(desk.viewer, desk.space_id, limit=2)
    for row, made, who in (
        (board["rows"][0], mine, desk.id_of("editor")),
        (board["rows"][1], loose, "none"),
    ):
        cell = _cell(row, open_["id"])
        assert cell["count"] == 3 and len(cell["items"]) == 2 and cell["next_cursor"]
        r = await desk.viewer.get(
            f"/api/spaces/{desk.space_id}/board/{open_['id']}",
            params={"assignee": who, "cursor": cell["next_cursor"], "limit": 2},
        )
        assert r.status_code == 200, r.text
        assert [t["id"] for t in cell["items"] + r.json()["items"]] == [t["id"] for t in made]
        listed = await desk.viewer.get(
            "/api/tickets", params={"space_id": desk.space_id, "assignee": who}
        )
        assert len(listed.json()["items"]) == 3


async def test_the_daily_shows_a_sprint_only(desk: Desk) -> None:
    sprint = await new_sprint(desk.moderator, desk.space_id)
    inside = await new_ticket(desk.editor, desk.space_id, "Drin", assignee=_me(desk, "editor"))
    inside = (await patch(desk.editor, inside, sprint_id=sprint["id"])).json()
    await new_ticket(desk.moderator, desk.space_id, "Draußen", assignee=_me(desk, "viewer"))
    board = await _daily(desk.viewer, desk.space_id, sprint=sprint["id"])
    assert [r["assignee"]["name"] for r in board["rows"]] == ["Desk editor"]
    shown = {t["id"] for r in board["rows"] for c in r["cells"] for t in c["items"]}
    assert shown == {inside["id"]}


async def test_the_daily_names_nothing_of_other_spaces(desk: Desk, make_space: MakeSpace) -> None:
    """Review focus 1 and 4 (mutation probe: without the space filter in the grouped
    query, the hidden space's tickets and their assignee appear)."""
    secret = await make_space(
        "team",
        "Geheim",
        members=[(desk.users["moderator"], "moderator"), (desk.users["editor2"], "editor")],
    )
    await new_ticket(desk.moderator, secret.id, "Geheim", assignee=_me(desk, "editor2"))
    await new_ticket(desk.editor, desk.space_id, "Hier", assignee=_me(desk, "editor"))
    board = await _daily(desk.viewer, desk.space_id)
    assert [r["assignee"]["name"] for r in board["rows"]] == ["Desk editor"]
    r = await desk.outsider.get(
        f"/api/spaces/{desk.space_id}/board", params={"group_by": "assignee"}
    )
    assert (r.status_code, r.json()["error"]["code"]) == (404, "space.not_found")
    r = await desk.viewer.get(f"/api/spaces/{secret.id}/board", params={"group_by": "assignee"})
    assert r.status_code == 404


async def test_the_highlight_agrees_with_the_timeline(desk: Desk, session: AsyncSession) -> None:
    """Review focus 4: a card is `changed` exactly when its thread has a status entry
    (or its creation) since the last working day began."""
    active = await status_of(desk.viewer, desk.space_id, "active")
    old = await new_ticket(desk.editor, desk.space_id, "Alt", assignee=_me(desk, "editor"))
    moved = await new_ticket(desk.editor, desk.space_id, "Neu", assignee=_me(desk, "editor"))
    moved = (await patch(desk.editor, moved, status_id=active["id"])).json()
    await ticket_handlers(session)
    since = last_working_day_start(datetime.now(UTC))
    for ticket in (old,):  # its status (creation) lies before the last working day
        await _changed_before(session, ticket, since)
        thread = await ticket_thread(desk.viewer, ticket)
        await session.execute(
            update(Message)
            .where(Message.conversation_id == thread["id"])
            .values(created_at=since - timedelta(minutes=1))
        )
    board = await _daily(desk.viewer, desk.space_id)
    cards = {t["id"]: t for r in board["rows"] for c in r["cells"] for t in c["items"]}
    for ticket in (old, moved):
        items = await messages(desk.viewer, (await ticket_thread(desk.viewer, ticket))["id"])
        status_entries = [
            datetime.fromisoformat(m["created_at"])
            for m in items
            if m["system"] and m["system"]["key"] in ("ticket.created", "ticket.status_changed")
        ]
        assert cards[ticket["id"]]["changed"] == (max(status_entries) >= since), ticket["title"]
    assert cards[moved["id"]]["changed"] and not cards[old["id"]]["changed"]


async def test_the_daily_takes_a_fixed_number_of_queries(desk: Desk, session: AsyncSession) -> None:
    async def calls() -> int:
        with _counting(session) as statements:
            await _daily(desk.viewer, desk.space_id)
        return len(statements)

    await new_ticket(desk.editor, desk.space_id, "Eins", assignee=_me(desk, "editor"))
    few = await calls()
    for name in ("manager", "moderator", "editor2", "viewer"):
        for status in await statuses(desk.viewer, desk.space_id):
            await new_ticket(
                desk.moderator, desk.space_id, "T", assignee=_me(desk, name), status_id=status["id"]
            )
    await new_ticket(desk.editor, desk.space_id, "Niemand")
    assert await calls() == few
