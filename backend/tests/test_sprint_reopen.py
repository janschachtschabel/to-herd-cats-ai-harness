"""A ticket of a closed sprint that goes back to an unfinished category returns to the
backlog in the same change (module review M4b, finding 3): one `ticket.updated` event
with the fields `status` and `sprint`, a timeline entry for each; the closed sprint's
tally stays as recorded. The same for a status change through my board
(`move-category`) and for a status deleted with an unfinished replacement. A ticket
that stays finished, or whose sprint is still open, keeps its sprint; a sprint the
request names itself wins."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from tests.factories_sprints import close, sprints, started
from tests.factories_tickets import Desk, new_ticket, patch, status_of
from tests.page_thread_helpers import messages
from tests.ticket_thread_helpers import ticket_handlers, ticket_thread


async def _closed_with_done(desk: Desk, *names: str) -> tuple[dict[str, Any], list[Any]]:
    """A closed sprint holding a done ticket per name (as they are after the close)."""
    sprint = await started(desk.moderator, desk.space_id)
    done = await status_of(desk.viewer, desk.space_id, "done")
    made = []
    for name in names:
        ticket = await new_ticket(desk.editor, desk.space_id, name, status_id=done["id"])
        r = await patch(desk.editor, ticket, sprint_id=sprint["id"])
        assert r.status_code == 200, r.text
        made.append(r.json())
    r = await close(desk.moderator, sprint, "backlog")
    assert r.status_code == 200, r.text
    return r.json(), made


async def _backlog(desk: Desk) -> set[str]:
    r = await desk.viewer.get(
        "/api/tickets", params={"space_id": desk.space_id, "sprint": "none", "limit": 100}
    )
    return {t["id"] for t in r.json()["items"]}


async def _payloads(session: AsyncSession, ticket_id: str) -> list[dict[str, Any]]:
    rows = await session.scalars(
        select(EventOutbox.payload)
        .where(
            EventOutbox.type == "ticket.updated",
            EventOutbox.payload["ticket_id"].astext == ticket_id,
        )
        .order_by(EventOutbox.id)
    )
    return list(rows)


async def test_a_reopened_ticket_returns_to_the_backlog(desk: Desk, session: AsyncSession) -> None:
    sprint, (ticket,) = await _closed_with_done(desk, "Wieder offen")
    open_ = await status_of(desk.viewer, desk.space_id, "open")
    r = await patch(desk.editor, ticket, status_id=open_["id"])
    assert r.status_code == 200, r.text
    reopened = r.json()
    assert reopened["sprint_id"] is None and reopened["version"] == ticket["version"] + 1
    assert reopened["id"] in await _backlog(desk)
    (listed,) = await sprints(desk.viewer, desk.space_id)
    assert listed["tally"] == sprint["tally"] == {"planned": 1, "done": 1, "carried": 0}
    last = (await _payloads(session, ticket["id"]))[-1]
    assert last["fields"] == ["sprint", "status"]
    assert last["changes"] == {
        "sprint": {"from": sprint["id"], "to": None},
        "status": {"from": ticket["status"]["id"], "to": open_["id"]},
    }
    await ticket_handlers(session)
    items = await messages(desk.viewer, (await ticket_thread(desk.viewer, ticket))["id"])
    keys = [m["system"]["key"] for m in items if m["system"]]
    assert keys[-2:] in (
        ["ticket.status_changed", "ticket.sprint_changed"],
        ["ticket.sprint_changed", "ticket.status_changed"],
    )
    entry = next(
        m["system"] for m in reversed(items) if m["system"]["key"] == "ticket.sprint_changed"
    )
    assert entry["old"] == {"value": sprint["id"], "name": sprint["name"]} and entry["new"] is None


async def test_a_finished_ticket_or_an_open_sprint_keeps_its_sprint(desk: Desk) -> None:
    sprint, (ticket, other) = await _closed_with_done(desk, "Verworfen", "Anderswo")
    cancelled = await status_of(desk.viewer, desk.space_id, "cancelled")
    active = await status_of(desk.viewer, desk.space_id, "active")
    r = await patch(desk.editor, ticket, status_id=cancelled["id"])
    assert (r.status_code, r.json()["sprint_id"]) == (200, sprint["id"])
    running = await started(desk.moderator, desk.space_id, "Nächster")
    r = await patch(desk.editor, other, status_id=active["id"], sprint_id=running["id"])
    assert (r.status_code, r.json()["sprint_id"]) == (200, running["id"])  # named: it wins
    r = await patch(desk.editor, r.json(), status_id=cancelled["id"])
    r = await patch(desk.editor, r.json(), status_id=active["id"])
    assert (r.status_code, r.json()["sprint_id"]) == (200, running["id"])  # sprint still open


async def test_moving_to_a_column_of_my_board_reopens_the_same_way(desk: Desk) -> None:
    sprint, (ticket,) = await _closed_with_done(desk, "Mein Board")
    r = await desk.editor.post(
        f"/api/tickets/{ticket['number']}/move-category",
        json={"category": "active", "version": ticket["version"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sprint_id"] is None and r.json()["status"]["category"] == "active"
    assert ticket["id"] in await _backlog(desk)


async def test_a_status_deleted_into_an_unfinished_one_reopens_into_the_backlog(
    desk: Desk, session: AsyncSession
) -> None:
    url = f"/api/spaces/{desk.space_id}/ticket-statuses"
    shipped = (await desk.admin.post(url, json={"name": "Geliefert", "category": "done"})).json()
    kept = (await desk.admin.post(url, json={"name": "Abgelegt", "category": "done"})).json()
    sprint = await started(desk.moderator, desk.space_id)
    made = {}
    for name, status in (("a", shipped), ("b", kept)):
        ticket = await new_ticket(desk.editor, desk.space_id, name, status_id=status["id"])
        made[name] = (await patch(desk.editor, ticket, sprint_id=sprint["id"])).json()
    sprint = (await close(desk.moderator, sprint, "backlog")).json()
    running = await started(desk.moderator, desk.space_id, "Läuft")
    live = await new_ticket(desk.editor, desk.space_id, "live", status_id=shipped["id"])
    live = (await patch(desk.editor, live, sprint_id=running["id"])).json()
    review = await status_of(desk.viewer, desk.space_id, "review")
    done = await status_of(desk.viewer, desk.space_id, "done")
    r = await desk.admin.delete(
        f"/api/ticket-statuses/{kept['id']}",
        params={"version": kept["version"], "replace_with": done["id"]},
    )
    assert r.status_code == 204, r.text
    r = await desk.admin.delete(
        f"/api/ticket-statuses/{shipped['id']}",
        params={"version": shipped["version"], "replace_with": review["id"]},
    )
    assert r.status_code == 204, r.text
    a, b, still = [
        (await desk.viewer.get(f"/api/tickets/{t['number']}")).json()
        for t in (made["a"], made["b"], live)
    ]
    assert (a["sprint_id"], a["status"]["id"]) == (None, review["id"])
    assert (b["sprint_id"], b["status"]["id"]) == (sprint["id"], done["id"])  # still finished
    assert (still["sprint_id"], still["status"]["id"]) == (running["id"], review["id"])
    (listed,) = [s for s in await sprints(desk.viewer, desk.space_id) if s["id"] == sprint["id"]]
    assert listed["tally"] == {"planned": 2, "done": 2, "carried": 0}
    last = (await _payloads(session, made["a"]["id"]))[-1]
    assert last["changes"] == {
        "sprint": {"from": sprint["id"], "to": None},
        "status": {"from": shipped["id"], "to": review["id"]},
    }
    assert (await _payloads(session, live["id"]))[-1]["fields"] == ["status"]


async def test_a_status_that_becomes_unfinished_reopens_into_the_backlog(
    desk: Desk, session: AsyncSession
) -> None:
    url = f"/api/spaces/{desk.space_id}/ticket-statuses"
    shipped = (await desk.admin.post(url, json={"name": "Geliefert", "category": "done"})).json()
    sprint = await started(desk.moderator, desk.space_id)
    old = await new_ticket(desk.editor, desk.space_id, "alt", status_id=shipped["id"])
    old = (await patch(desk.editor, old, sprint_id=sprint["id"])).json()
    sprint = (await close(desk.moderator, sprint, "backlog")).json()
    running = await started(desk.moderator, desk.space_id, "Läuft")
    live = await new_ticket(desk.editor, desk.space_id, "live", status_id=shipped["id"])
    live = (await patch(desk.editor, live, sprint_id=running["id"])).json()
    r = await desk.admin.patch(
        f"/api/ticket-statuses/{shipped['id']}",
        json={"version": shipped["version"], "category": "cancelled"},
    )
    assert r.status_code == 200, r.text
    got = (await desk.viewer.get(f"/api/tickets/{old['number']}")).json()
    assert got["sprint_id"] == sprint["id"]  # still finished
    r = await desk.admin.patch(
        f"/api/ticket-statuses/{shipped['id']}",
        json={"version": r.json()["version"], "category": "active"},
    )
    assert r.status_code == 200, r.text
    got, still = [
        (await desk.viewer.get(f"/api/tickets/{t['number']}")).json() for t in (old, live)
    ]
    assert got["sprint_id"] is None and got["version"] == old["version"] + 1
    assert still["sprint_id"] == running["id"] and still["version"] == live["version"]
    assert got["id"] in await _backlog(desk)
    (last,) = (await _payloads(session, old["id"]))[-1:]
    assert last["changes"] == {"sprint": {"from": sprint["id"], "to": None}}
    assert len(await _payloads(session, live["id"])) == 1  # put into the sprint only
