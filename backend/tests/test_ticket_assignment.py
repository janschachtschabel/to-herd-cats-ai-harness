"""Assigning tickets (plan M4 task 2): who may assign whom, taking and letting go, and
who can be an assignee at all (split from `test_tickets.py`, review M4 P9)."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.modules.orgs.models import Organization
from tests.factories import MakeUser
from tests.factories_tickets import Desk, new_ticket, patch


def _without_trace(response: Any) -> dict[str, Any]:
    error: dict[str, Any] = response.json()["error"]
    return {k: v for k, v in error.items() if k != "trace_id"}


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
