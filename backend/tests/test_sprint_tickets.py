"""Tickets in sprints (plan M4b task 1, decisions 1 and 3): a ticket is in at most one
planned or active sprint of its own space (`ticket.edit`, with the version read);
anything else is 422 `ticket.sprint_invalid`, the same for a sprint of another space
as for one nobody has. The list and the board filter by sprint (`sprint=none`: the
backlog). Closing a sprint moves its unfinished tickets to the next planned sprint or
back to the backlog, keeps its tally and writes one event per moved ticket; each
sprint change of a ticket is one timeline entry `ticket.sprint_changed`."""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from tests.factories_spaces import MakeSpace
from tests.factories_sprints import close, new_sprint, started
from tests.factories_tickets import Desk, new_ticket, patch, status_of
from tests.page_thread_helpers import messages
from tests.ticket_thread_helpers import ticket_handlers, ticket_thread


async def _ids(client: AsyncClient, **params: Any) -> set[str]:
    r = await client.get("/api/tickets", params={"limit": 100, **params})
    assert r.status_code == 200, r.text
    return {t["id"] for t in r.json()["items"]}


async def _in_sprint(
    client: AsyncClient, ticket: dict[str, Any], sprint_id: str | None
) -> dict[str, Any]:
    r = await patch(client, ticket, sprint_id=sprint_id)
    assert r.status_code == 200, r.text
    moved: dict[str, Any] = r.json()
    return moved


async def test_editors_put_tickets_into_sprints_of_their_space_only(
    desk: Desk, make_space: MakeSpace
) -> None:
    sprint = await new_sprint(desk.moderator, desk.space_id)
    ticket = await new_ticket(desk.editor, desk.space_id)
    assert ticket["sprint_id"] is None
    r = await patch(desk.viewer, ticket, sprint_id=sprint["id"])
    assert r.status_code == 403
    moved = await _in_sprint(desk.editor, ticket, sprint["id"])
    assert (moved["sprint_id"], moved["version"]) == (sprint["id"], 2)
    stale = await patch(desk.editor, ticket, sprint_id=None)
    assert stale.status_code == 409
    other = await make_space("team", "Anders", members=[(desk.users["moderator"], "moderator")])
    foreign = await new_sprint(desk.moderator, other.id)
    closed = await started(desk.moderator, desk.space_id, "Vorbei")
    closed = (await close(desk.moderator, closed, "backlog")).json()
    answers = []
    for target in (foreign["id"], str(uuid.uuid4()), closed["id"]):
        r = await patch(desk.moderator, moved, sprint_id=target)
        assert r.status_code == 422, r.text
        answers.append((r.json()["error"]["code"], r.json()["error"]["message"]))
    assert set(answers) == {("ticket.sprint_invalid", answers[0][1])}
    back = await _in_sprint(desk.editor, moved, None)
    assert back["sprint_id"] is None


async def test_the_database_keeps_a_ticket_in_a_sprint_of_its_space(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    other = await make_space("team", "Anders", members=[(desk.users["moderator"], "moderator")])
    foreign = await new_sprint(desk.moderator, other.id)
    ticket = await new_ticket(desk.editor, desk.space_id)
    savepoint = await session.begin_nested()
    try:
        await session.execute(
            text("UPDATE work_item SET sprint_id = :s WHERE id = :t"),
            {"s": foreign["id"], "t": ticket["id"]},
        )
        raise AssertionError("a sprint of another space was accepted")
    except IntegrityError:
        await savepoint.rollback()
    second = await new_sprint(desk.moderator, desk.space_id, "Zwei")
    await started(desk.moderator, desk.space_id, "Eins")
    savepoint = await session.begin_nested()
    try:
        await session.execute(
            text("UPDATE sprint SET state = 'active' WHERE id = :s"), {"s": second["id"]}
        )
        raise AssertionError("a second active sprint was accepted")
    except IntegrityError:
        await savepoint.rollback()


async def test_list_and_board_filter_by_sprint_and_backlog(
    desk: Desk, make_space: MakeSpace
) -> None:
    sprint = await new_sprint(desk.moderator, desk.space_id)
    inside = await _in_sprint(
        desk.editor, await new_ticket(desk.editor, desk.space_id), sprint["id"]
    )
    outside = await new_ticket(desk.editor, desk.space_id)
    assert await _ids(desk.viewer, sprint=sprint["id"]) == {inside["id"]}
    assert await _ids(desk.viewer, space_id=desk.space_id, sprint="none") == {outside["id"]}
    board = (
        await desk.viewer.get(f"/api/spaces/{desk.space_id}/board", params={"sprint": "none"})
    ).json()
    assert {t["id"] for c in board["columns"] for t in c["items"]} == {outside["id"]}
    open_ = await status_of(desk.viewer, desk.space_id, "open")
    column = await desk.viewer.get(
        f"/api/spaces/{desk.space_id}/board/{open_['id']}", params={"sprint": sprint["id"]}
    )
    assert [t["id"] for t in column.json()["items"]] == [inside["id"]]
    other = await make_space("team", "Anders", members=[(desk.users["viewer"], "viewer")])
    foreign = await new_sprint(desk.admin, other.id)
    assert await _ids(desk.viewer, sprint=foreign["id"]) == set()
    r = await desk.viewer.get("/api/tickets", params={"sprint": "bald"})
    assert r.status_code == 422


async def test_closing_moves_the_unfinished_to_the_backlog_and_keeps_the_tally(
    desk: Desk, session: AsyncSession
) -> None:
    sprint = await started(desk.moderator, desk.space_id)
    done = await status_of(desk.viewer, desk.space_id, "done")
    cancelled = await status_of(desk.viewer, desk.space_id, "cancelled")
    review = await status_of(desk.viewer, desk.space_id, "review")
    tickets = {}
    for name, status in (("done", done), ("gone", cancelled), ("review", review), ("new", None)):
        made = await new_ticket(
            desk.editor, desk.space_id, name, **({"status_id": status["id"]} if status else {})
        )
        tickets[name] = await _in_sprint(desk.editor, made, sprint["id"])
    before = await _count_events(session)
    r = await close(desk.moderator, sprint, "backlog")
    assert r.status_code == 200, r.text
    assert r.json()["tally"] == {"planned": 4, "done": 1, "carried": 2}
    assert await _ids(desk.viewer, sprint=sprint["id"]) == {
        tickets["done"]["id"],
        tickets["gone"]["id"],
    }
    backlog = await _ids(desk.viewer, space_id=desk.space_id, sprint="none")
    assert backlog == {tickets["review"]["id"], tickets["new"]["id"]}
    moved = (await desk.viewer.get(f"/api/tickets/{tickets['new']['number']}")).json()
    assert moved["version"] == tickets["new"]["version"] + 1
    after = await _count_events(session)
    grown = {t: n - before.get(t, 0) for t, n in after.items() if n != before.get(t, 0)}
    assert grown == {"ticket.updated": 2, "sprint.closed": 1}
    await ticket_handlers(session)
    items = await messages(desk.viewer, (await ticket_thread(desk.viewer, moved))["id"])
    entries = [
        m["system"] for m in items if m["system"] and m["system"]["key"] == "ticket.sprint_changed"
    ]
    assert len(entries) == 2  # put in, then taken out on closing
    assert entries[-1]["old"] == {"value": sprint["id"], "name": sprint["name"]}
    assert entries[-1]["new"] is None


async def test_closing_into_the_next_planned_sprint(desk: Desk, session: AsyncSession) -> None:
    sprint = await started(desk.moderator, desk.space_id)
    lone = await close(desk.moderator, sprint, "next")
    assert (lone.status_code, lone.json()["error"]["code"]) == (422, "sprint.next_missing")
    later = await new_sprint(desk.moderator, desk.space_id, "Später", "2027-02-01", "2027-02-12")
    after = await new_sprint(desk.moderator, desk.space_id, "Danach", "2026-12-01", "2026-12-12")
    ticket = await _in_sprint(
        desk.editor, await new_ticket(desk.editor, desk.space_id), sprint["id"]
    )
    r = await close(desk.moderator, sprint, "next")
    assert r.status_code == 200, r.text
    assert r.json()["tally"] == {"planned": 1, "done": 0, "carried": 1}
    assert await _ids(desk.viewer, sprint=after["id"]) == {ticket["id"]}
    assert await _ids(desk.viewer, sprint=later["id"]) == set()
    await ticket_handlers(session)
    items = await messages(desk.viewer, (await ticket_thread(desk.viewer, ticket))["id"])
    entry = [
        m["system"] for m in items if m["system"] and m["system"]["key"] == "ticket.sprint_changed"
    ][-1]
    assert entry["old"]["name"] == sprint["name"] and entry["new"]["name"] == "Danach"


async def test_one_timeline_entry_per_sprint_change_however_often_delivered(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    sprint = await new_sprint(desk.moderator, desk.space_id, "Eins")
    ticket = await _in_sprint(
        desk.editor, await new_ticket(desk.editor, desk.space_id), sprint["id"]
    )
    await ticket_handlers(session)
    await ticket_handlers(session)
    thread = await ticket_thread(desk.viewer, ticket)
    items = await messages(desk.viewer, thread["id"])
    keys = [m["system"]["key"] for m in items if m["system"]]
    assert keys.count("ticket.sprint_changed") == 1
    entry = next(
        m["system"] for m in items if m["system"] and m["system"]["key"] == "ticket.sprint_changed"
    )
    assert entry["old"] is None and entry["new"] == {"value": sprint["id"], "name": "Eins"}
    events = await session.scalars(
        select(EventOutbox.payload).where(EventOutbox.type == "ticket.updated")
    )
    (payload,) = list(events)
    assert payload["fields"] == ["sprint"]
    assert payload["changes"] == {"sprint": {"from": None, "to": sprint["id"]}}


async def _count_events(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(select(EventOutbox.type, func.count()).group_by(EventOutbox.type))
    return dict(rows.all())  # type: ignore[arg-type]


async def test_a_ticket_names_its_sprint_however_many_the_space_has(desk: Desk) -> None:
    """Module review M4b, finding 10: the ticket carries its sprint's id, name and
    state (a sprint of its own space, so whoever sees the ticket may see it), not only
    an id the client would have to find among the first 100 sprints."""
    sprint = await new_sprint(desk.moderator, desk.space_id, "Benannt")
    ticket = await new_ticket(desk.editor, desk.space_id)
    assert ticket["sprint"] is None
    moved = await _in_sprint(desk.editor, ticket, sprint["id"])
    assert moved["sprint"] == {"id": sprint["id"], "name": "Benannt", "state": "planned"}
    shown = (await desk.viewer.get(f"/api/tickets/{ticket['number']}")).json()
    assert shown["sprint"] == moved["sprint"]
    listed = (await desk.viewer.get("/api/tickets", params={"sprint": sprint["id"]})).json()
    assert "sprint" not in listed["items"][0]  # rows keep the id only
