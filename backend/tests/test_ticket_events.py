"""The events and audit entries of ticket changes (plan M4 task 2): exactly one event
per change, ids only, and the audited actions (split from `test_tickets.py`, review M4
P9)."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.modules.audit.models import AuditLog
from tests.factories_tickets import Desk, new_ticket, patch, status_of


async def _events(session: AsyncSession) -> list[EventOutbox]:
    rows = await session.scalars(
        select(EventOutbox).where(EventOutbox.type.like("ticket.%")).order_by(EventOutbox.id)
    )
    return list(rows.all())


def _ref(desk: Desk, name: str) -> dict[str, str]:
    return {"type": "user", "id": desk.id_of(name)}


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
