"""Tickets (plan M4 task 2): create, read, change and assign, with the rights of the
ticket's space, versions, and exactly one event per change."""

import json
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.actor import Actor
from app.core.errors import NotFound
from app.core.outbox import EventOutbox
from app.core.pagination import PageParams
from app.core.principal import Principal, SystemRole
from app.modules.audit.models import AuditLog
from app.modules.orgs.models import Organization
from app.modules.tickets.listing import Filters, Sort
from app.modules.tickets.service import TicketService
from app.modules.users.models import User
from tests.factories import MakeUser
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket, patch, status_of


async def _events(session: AsyncSession) -> list[EventOutbox]:
    rows = await session.scalars(
        select(EventOutbox).where(EventOutbox.type.like("ticket.%")).order_by(EventOutbox.id)
    )
    return list(rows.all())


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


def _ref(desk: Desk, name: str) -> dict[str, str]:
    return {"type": "user", "id": desk.id_of(name)}


async def test_assigning_others_needs_ticket_assign(desk: Desk) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    r = await patch(desk.editor, ticket, assignee=_ref(desk, "editor2"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "auth.permission_denied"
    r = await patch(desk.moderator, ticket, assignee=_ref(desk, "editor2"))
    assert r.status_code == 200, r.text
    assert r.json()["assignee"]["id"] == desk.id_of("editor2")
    r = await patch(desk.editor, r.json(), assignee=None)  # someone else's assignment
    assert r.status_code == 403
    r = await desk.editor.post(
        f"/api/spaces/{desk.space_id}/tickets",
        json={"title": "X", "assignee": _ref(desk, "editor2")},
    )
    assert r.status_code == 403


async def test_an_editor_takes_an_unassigned_ticket_and_lets_go(desk: Desk) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    taken = await patch(desk.editor2, ticket, assignee=_ref(desk, "editor2"))
    assert taken.status_code == 200, taken.text
    assert taken.json()["assignee"]["name"] == "Desk editor2"
    r = await patch(desk.editor, taken.json(), assignee=_ref(desk, "editor"))
    assert r.status_code == 403  # taking it from someone else needs ticket.assign
    released = await patch(desk.editor2, taken.json(), assignee=None)
    assert released.status_code == 200
    assert released.json()["assignee"] is None
    own = await new_ticket(desk.editor, desk.space_id, assignee=_ref(desk, "editor"))
    assert own["assignee"]["id"] == desk.id_of("editor")
    viewer = await patch(desk.viewer, released.json(), assignee=_ref(desk, "viewer"))
    assert viewer.status_code == 403  # no ticket.edit


async def test_only_people_who_see_the_space_can_be_assigned(
    desk: Desk, session: AsyncSession, make_user: MakeUser
) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    gone = await make_user(is_active=False)
    other = Organization(name="Andere")
    session.add(other)
    await session.flush()
    foreign = await make_user(organization=other)
    answers = []
    for person in (desk.id_of("outsider"), str(gone.id), str(foreign.id), str(uuid7())):
        r = await patch(desk.moderator, ticket, assignee={"type": "user", "id": person})
        assert r.status_code == 422, r.text
        answers.append(_without_trace(r))
    assert all(a == answers[0] for a in answers)
    assert answers[0]["code"] == "ticket.assignee_invalid"
    r = await patch(desk.moderator, ticket, assignee={"type": "group", "id": str(uuid7())})
    assert r.status_code == 422
    r = await patch(desk.moderator, ticket, assignee=_ref(desk, "viewer"))
    assert r.status_code == 200  # a viewer may read tickets


async def test_an_assignee_who_lost_access_stays_by_name(desk: Desk, session: AsyncSession) -> None:
    from app.core.principal import Principal
    from app.modules.spaces.repository import SpaceRepository

    ticket = await new_ticket(desk.moderator, desk.space_id, assignee=_ref(desk, "editor2"))
    await SpaceRepository(session).remove_member(
        desk.space.id, Principal.user(desk.users["editor2"].id)
    )
    r = await desk.viewer.get(f"/api/tickets/{ticket['number']}")
    assert r.json()["assignee"] == {
        "type": "user",
        "id": desk.id_of("editor2"),
        "name": "Desk editor2",
    }
    assert (await desk.editor2.get(f"/api/tickets/{ticket['number']}")).status_code == 404


async def test_every_change_is_one_event_with_ids_only(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id, "Geheimer Titel")
    active = await status_of(desk.viewer, desk.space_id, "active")
    r = await patch(
        desk.moderator,
        ticket,
        title="Noch geheimer",
        description_md="Geheimer Text",
        status_id=active["id"],
        priority="high",
        assignee=_ref(desk, "editor"),
        due_on="2027-02-01",
        kind="bug",
    )
    assert r.status_code == 200, r.text
    nothing = await patch(desk.moderator, r.json(), title="Noch geheimer")
    assert nothing.json()["version"] == r.json()["version"]  # no change, no new version
    created, updated = await _events(session)
    assert (created.type, updated.type) == ("ticket.created", "ticket.updated")
    assert created.subject_type == updated.subject_type == "ticket"
    assert str(created.subject_id) == str(updated.subject_id) == ticket["id"]
    assert str(updated.space_id) == desk.space_id
    payload = updated.payload
    assert payload["ticket_id"] == ticket["id"]
    assert payload["fields"] == [
        "assignee",
        "description",
        "due_on",
        "kind",
        "priority",
        "status",
        "title",
    ]
    assert payload["changes"] == {
        "assignee": {"from": None, "to": desk.id_of("editor")},
        "due_on": {"from": None, "to": "2027-02-01"},
        "kind": {"from": "task", "to": "bug"},
        "priority": {"from": "normal", "to": "high"},
        "status": {"from": ticket["status"]["id"], "to": active["id"]},
    }
    text = json.dumps([created.payload, updated.payload])
    assert "geheim" not in text.lower()


async def test_creating_assigning_and_cancelling_are_audited(
    desk: Desk, session: AsyncSession
) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    assigned = await patch(desk.moderator, ticket, assignee=_ref(desk, "editor2"))
    cancelled = await status_of(desk.viewer, desk.space_id, "cancelled")
    r = await patch(desk.editor, assigned.json(), status_id=cancelled["id"], title="Egal")
    assert r.status_code == 200
    rows = await session.execute(
        select(AuditLog.action, AuditLog.details)
        .where(AuditLog.target_type == "ticket")
        .order_by(AuditLog.id)
    )
    entries = rows.all()
    assert [action for action, _ in entries] == [
        "ticket.created",
        "ticket.assigned",
        "ticket.cancelled",
    ]
    assert entries[1][1]["to"] == desk.id_of("editor2")


async def test_a_deleted_status_moves_its_tickets_with_an_event_each(
    desk: Desk, session: AsyncSession
) -> None:
    review = await status_of(desk.viewer, desk.space_id, "review")
    active = await status_of(desk.viewer, desk.space_id, "active")
    one = await new_ticket(desk.editor, desk.space_id, status_id=review["id"])
    two = await new_ticket(desk.editor, desk.space_id, status_id=review["id"])
    r = await desk.manager.delete(
        f"/api/ticket-statuses/{review['id']}",
        params={"version": review["version"], "replace_with": active["id"]},
    )
    assert r.status_code == 204
    updated = [e for e in await _events(session) if e.type == "ticket.updated"]
    assert sorted(e.payload["ticket_id"] for e in updated) == sorted([one["id"], two["id"]])
    assert all(
        e.payload["changes"] == {"status": {"from": review["id"], "to": active["id"]}}
        for e in updated
    )
    moved = (await desk.viewer.get(f"/api/tickets/{one['number']}")).json()
    assert (moved["status"]["id"], moved["version"]) == (active["id"], 2)


async def test_deactivated_people_do_not_act(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    user: User = desk.users["editor"]
    user.is_active = False
    await session.flush()
    r = await patch(desk.editor, ticket, title="X")
    assert r.status_code == 401
