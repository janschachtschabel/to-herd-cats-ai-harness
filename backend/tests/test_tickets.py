"""Tickets (plan M4 task 2): create, read and change, with the rights of the ticket's
space and versions. Assigning: `test_ticket_assignment.py`; events and audit:
`test_ticket_events.py`."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.actor import Actor
from app.core.errors import NotFound
from app.core.pagination import PageParams
from app.core.principal import Principal, SystemRole
from app.modules.orgs.models import Organization
from app.modules.tickets.listing import Filters, Sort
from app.modules.tickets.service import TicketService
from app.modules.users.models import User
from tests.factories import MakeUser
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket, patch, status_of


def _without_trace(response: Any) -> dict[str, Any]:
    error: dict[str, Any] = response.json()["error"]
    return {k: v for k, v in error.items() if k != "trace_id"}


async def test_an_editor_creates_a_ticket(desk: Desk) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id, "Drucker reparieren")
    neu = await status_of(desk.viewer, desk.space_id, "open")
    assert ticket["key"] == f"HC-{ticket['number']}"
    assert ticket["number"] >= 1
    assert (ticket["title"], ticket["description_md"], ticket["kind"]) == (
        "Drucker reparieren",
        "",
        "task",
    )
    assert ticket["status"] == {"id": neu["id"], "name": "Neu", "category": "open"}
    assert (ticket["priority"], ticket["due_on"], ticket["parent"]) == ("normal", None, None)
    assert ticket["assignee"] is None
    assert ticket["reporter"] == {
        "type": "user",
        "id": desk.id_of("editor"),
        "name": "Desk editor",
    }
    assert ticket["space_id"] == desk.space_id
    assert ticket["version"] == 1
    assert ticket["children"] == {
        "open": 0,
        "active": 0,
        "review": 0,
        "done": 0,
        "cancelled": 0,
    }


async def test_numbers_count_up_per_organisation(desk: Desk, make_space: MakeSpace) -> None:
    other = await make_space("open", "Zweiter Bereich")
    first = await new_ticket(desk.editor, desk.space_id)
    second = await new_ticket(desk.admin, other.id)
    third = await new_ticket(desk.editor, desk.space_id)
    assert [second["number"], third["number"]] == [first["number"] + 1, first["number"] + 2]


@pytest.mark.parametrize(
    ("name", "status", "code"),
    [
        ("manager", 201, None),
        ("moderator", 201, None),
        ("editor", 201, None),
        ("admin", 201, None),
        ("viewer", 403, "auth.permission_denied"),
        ("outsider", 404, "space.not_found"),
    ],
)
async def test_creating_needs_ticket_create(
    desk: Desk, name: str, status: int, code: str | None
) -> None:
    r = await desk.clients[name].post(f"/api/spaces/{desk.space_id}/tickets", json={"title": "X"})
    assert r.status_code == status, r.text
    if code:
        assert r.json()["error"]["code"] == code


async def test_create_with_every_field(desk: Desk) -> None:
    review = await status_of(desk.viewer, desk.space_id, "review")
    ticket = await new_ticket(
        desk.moderator,
        desk.space_id,
        "Alles",
        description_md="# Ziel\n\nText",
        kind="bug",
        status_id=review["id"],
        priority="urgent",
        due_on="2026-12-24",
        assignee={"type": "user", "id": desk.id_of("editor")},
    )
    assert (ticket["kind"], ticket["priority"], ticket["due_on"]) == ("bug", "urgent", "2026-12-24")
    assert ticket["status"]["id"] == review["id"]
    assert ticket["description_md"] == "# Ziel\n\nText"
    assert ticket["assignee"] == {"type": "user", "id": desk.id_of("editor"), "name": "Desk editor"}


@pytest.mark.parametrize(
    "body",
    [
        {"title": ""},
        {"title": "x" * 201},
        {"title": "x", "description_md": "x" * 100_001},
        {"title": "x", "kind": "saga"},
        {"title": "x", "priority": "asap"},
        {"title": "x", "due_on": "morgen"},
        {"title": "x", "number": 5},
    ],
)
async def test_invalid_input_is_422(desk: Desk, body: dict[str, Any]) -> None:
    r = await desk.editor.post(f"/api/spaces/{desk.space_id}/tickets", json=body)
    assert r.status_code == 422, r.text


async def test_reading_by_number(desk: Desk, make_user: MakeUser, make_space: MakeSpace) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    for name in ("viewer", "editor", "admin"):
        r = await desk.clients[name].get(f"/api/tickets/{ticket['number']}")
        assert r.status_code == 200, name
        assert r.json()["id"] == ticket["id"]
    hidden = await desk.outsider.get(f"/api/tickets/{ticket['number']}")
    free = await desk.outsider.get(f"/api/tickets/{ticket['number'] + 1000}")
    assert hidden.status_code == free.status_code == 404
    assert _without_trace(hidden) == _without_trace(free)
    assert _without_trace(hidden)["code"] == "ticket.not_found"


async def test_a_ticket_of_another_organisation_does_not_exist(
    desk: Desk, session: AsyncSession, make_user: MakeUser
) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    other = Organization(name="Andere")
    session.add(other)
    await session.flush()
    stranger = await make_user(SystemRole.OWNER, organization=other)
    actor = Actor(other.id, Principal.user(stranger.id), SystemRole.OWNER, frozenset())
    service = TicketService(session)
    for attempt in (
        service.get(actor, ticket["number"]),
        service.update(actor, ticket["number"], 1, {"title": "X"}),
    ):
        with pytest.raises(NotFound) as hidden:
            await attempt
        assert hidden.value.code == "ticket.not_found"
    page = await service.list(actor, Filters(), Sort.NUMBER, PageParams())
    assert page.items == []


async def test_editing_needs_ticket_edit(desk: Desk) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    r = await patch(desk.viewer, ticket, title="Nein")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "auth.permission_denied"
    r = await patch(desk.outsider, ticket, title="Nein")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ticket.not_found"
    r = await patch(desk.editor2, ticket, title="Ja", priority="high", due_on="2027-01-31")
    assert r.status_code == 200, r.text
    changed = r.json()
    assert (changed["title"], changed["priority"], changed["due_on"]) == (
        "Ja",
        "high",
        "2027-01-31",
    )
    assert changed["version"] == 2
    r = await patch(desk.editor2, changed, due_on=None, description_md="Neu beschrieben")
    assert (r.json()["due_on"], r.json()["description_md"]) == (None, "Neu beschrieben")


async def test_a_status_comes_from_the_tickets_space(desk: Desk, make_space: MakeSpace) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    other = await make_space("open", "Fremd")
    foreign = await status_of(desk.admin, other.id, "active")
    for status_id in (foreign["id"], str(uuid7())):
        r = await patch(desk.editor, ticket, status_id=status_id)
        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "ticket.status_invalid"
        r = await desk.editor.post(
            f"/api/spaces/{desk.space_id}/tickets", json={"title": "X", "status_id": status_id}
        )
        assert r.json()["error"]["code"] == "ticket.status_invalid"
    active = await status_of(desk.viewer, desk.space_id, "active")
    r = await patch(desk.editor, ticket, status_id=active["id"])
    assert r.json()["status"] == {"id": active["id"], "name": "In Arbeit", "category": "active"}


async def test_an_old_version_is_a_conflict(desk: Desk) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    assert (await patch(desk.editor, ticket, title="Eins")).status_code == 200
    r = await patch(desk.editor2, ticket, title="Zwei")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ticket.version_conflict"
    assert r.json()["error"]["details"] == {"current_version": 2}


async def test_null_is_refused_where_a_value_is_required(desk: Desk) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    for field in ("title", "kind", "status_id", "priority", "description_md"):
        r = await patch(desk.editor, ticket, **{field: None})
        assert r.status_code == 422, field
    assert (await patch(desk.editor, ticket, colour="red")).status_code == 422


async def test_deactivated_people_do_not_act(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    user: User = desk.users["editor"]
    user.is_active = False
    await session.flush()
    r = await patch(desk.editor, ticket, title="X")
    assert r.status_code == 401
