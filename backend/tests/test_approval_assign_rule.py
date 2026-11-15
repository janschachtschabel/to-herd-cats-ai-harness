"""Carry-in from M7 (M6 bug): a released `assign_ticket` is checked by the rule the
ticket service enforces (`tickets/assignment.assignment_action`), at the decision and
again when the call runs. Taking an unassigned ticket for oneself needs `ticket.edit`,
so an editor-level run's released self-assignment runs; assigning someone else still
needs `ticket.assign`."""

from typing import Any

from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.run_models import StopReason
from app.modules.spaces.repository import SpaceRepository
from app.modules.tickets.models import WorkItem
from tests.factories_tools import call
from tests.factories_writing import Work, set_level
from tests.test_approvals import confirm, decide


async def _asked(work: Work, ticket: dict[str, Any], assignee: str) -> dict[str, Any]:
    await set_level(work.bench, 3)  # assigning is a level-3 tool; the grant tightens it
    await confirm(work, "assign_ticket")
    args = {
        "key": f"HC-{ticket['number']}",
        "assignee_type": "user",
        "assignee_id": assignee,
        "reason": "Ich übernehme.",
    }
    work.bench.stub.state.replies.extend([call("assign_ticket", **args), {"content": "Ok."}])
    await work.bench.say("Bitte zuweisen")
    assert await work.bench.run_next() is None  # waits for the release
    r = await work.bench.people.alice.get("/api/approvals", params={"state": "pending"})
    (approval,) = r.json()["items"]
    return dict(approval)


async def _assignee(work: Work, number: object) -> object:
    row = await work.bench.session.scalar(
        select(WorkItem).where(WorkItem.number == number).execution_options(populate_existing=True)
    )
    assert row is not None
    return row.assignee_id


async def test_an_editor_releases_taking_a_ticket_for_herself(work: Work) -> None:
    ticket = await work.ticket()
    alice = work.bench.people.users["alice"]
    approval = await _asked(work, ticket, str(alice.id))
    r = await decide(work, approval, "approve")
    assert r.status_code == 200, r.text
    assert await work.bench.run_next() == StopReason.COMPLETED
    assert await _assignee(work, ticket["number"]) == alice.id


async def test_a_moderator_releases_it_for_a_run_held_to_an_editor(work: Work) -> None:
    """The gate's check after the release used `ticket.assign` against the run's actor
    (Alice held to Ava's editor role): the run ended `rights_revoked`."""
    alice = work.bench.people.users["alice"]
    spaces = SpaceRepository(work.bench.session)
    await spaces.set_member(work.space.id, Principal.user(alice.id), SpaceRole.MODERATOR)
    ticket = await work.ticket()
    approval = await _asked(work, ticket, str(alice.id))
    assert (await decide(work, approval, "approve")).status_code == 200
    assert await work.bench.run_next() == StopReason.COMPLETED
    assert await _assignee(work, ticket["number"]) == alice.id


async def test_assigning_someone_else_still_needs_the_right_to_assign(work: Work) -> None:
    alice = work.bench.people.users["alice"]
    admin = work.bench.people.users["admin"]
    spaces = SpaceRepository(work.bench.session)
    await spaces.set_member(work.space.id, Principal.user(alice.id), SpaceRole.MODERATOR)
    ticket = await work.ticket()
    approval = await _asked(work, ticket, str(admin.id))
    assert (await decide(work, approval, "approve")).status_code == 200
    assert await work.bench.run_next() == StopReason.RIGHTS_REVOKED  # Ava is an editor
    assert await _assignee(work, ticket["number"]) is None
