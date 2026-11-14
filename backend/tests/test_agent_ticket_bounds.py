"""Bounds of an agent's work on tickets (review M6 finding 16): a ticket reassigned
away from an agent (to anyone else or nobody) asks that agent's open run on it to
stop, in the reassigning transaction, through the run's cancel request (the run that
hands it over itself goes on); and one run hands at most `MAX_HANDOVERS_PER_RUN`
tickets to agents, a tool error beyond."""

import re
from typing import Any

from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.models import MAX_HANDOVERS_PER_RUN, StopReason
from app.modules.agents.run_control_models import RunCancelRequest
from app.modules.spaces.repository import SpaceRepository
from tests.factories_tools import call
from tests.factories_writing import Work, set_level
from tests.test_agent_tickets import _assign, _bert, _handing, _runs


async def _reassign(work: Work, ticket: dict[str, Any], assignee: object) -> None:
    now = (await work.admin.get(f"/api/tickets/{ticket['number']}")).json()
    r = await work.admin.patch(
        f"/api/tickets/{ticket['number']}", json={"version": now["version"], "assignee": assignee}
    )
    assert r.status_code == 200, r.text


async def _cancel_requests(work: Work) -> list[RunCancelRequest]:
    return list((await work.bench.session.scalars(select(RunCancelRequest))).all())


async def test_reassigning_to_a_person_stops_the_agents_run_on_it(work: Work) -> None:
    ticket = await work.ticket()
    await _assign(work, ticket, work.bench.agent)
    (run,) = await _runs(work, work.bench.agent)
    alice = work.bench.people.users["alice"]
    await _reassign(work, ticket, {"type": "user", "id": str(alice.id)})
    (asked,) = await _cancel_requests(work)
    assert asked.run_id == run.id
    assert await work.bench.run_next() == StopReason.CANCELLED
    assert work.bench.stub.state.log == []


async def test_unassigning_stops_it_and_another_agent_starts_anew(work: Work) -> None:
    bert = await _bert(work)
    ticket = await work.ticket()
    await _assign(work, ticket, work.bench.agent)
    (run,) = await _runs(work, work.bench.agent)
    await _reassign(work, ticket, None)
    assert [c.run_id for c in await _cancel_requests(work)] == [run.id]
    assert await work.bench.run_next() == StopReason.CANCELLED
    await _reassign(work, ticket, {"type": "agent", "id": str(bert.id)})
    assert len(await _runs(work, bert)) == 1
    assert len(await _cancel_requests(work)) == 1  # the ended run is asked nothing more


async def test_the_run_that_hands_a_ticket_over_goes_on(work: Work) -> None:
    _, bert, first = await _handing(work)
    assert await work.bench.run_next() == StopReason.COMPLETED
    assert await _cancel_requests(work) == []
    assert len(await _runs(work, bert)) == 1


async def test_one_run_hands_at_most_five_tickets_to_agents(work: Work) -> None:
    bench = work.bench
    await set_level(bench, 3)
    await bench.join(work.space, SpaceRole.MODERATOR)  # may assign, as Alice may
    alice = Principal.user(bench.people.users["alice"].id)
    await SpaceRepository(bench.session).set_member(work.space.id, alice, SpaceRole.MODERATOR)
    bert = await _bert(work)
    tickets = [await work.ticket(f"Aufgabe {n}") for n in range(MAX_HANDOVERS_PER_RUN + 1)]
    hands = [
        call(
            "assign_ticket",
            key=f"HC-{t['number']}",
            assignee_type="agent",
            assignee_id=str(bert.id),
            reason="Bert macht das.",
        )
        for t in tickets
    ]
    bench.stub.state.replies.extend([*hands, {"content": "Verteilt."}])
    await bench.say("Verteile die Aufgaben an Bert")
    assert await bench.run_next() == StopReason.COMPLETED
    sent = bench.stub.state.texts()
    assert len(set(re.findall(r"Assigned HC-\d+", sent))) == MAX_HANDOVERS_PER_RUN
    assert f"Refused (run.handovers): a run hands at most {MAX_HANDOVERS_PER_RUN}" in sent
    last = (await work.admin.get(f"/api/tickets/{tickets[-1]['number']}")).json()
    assert last["assignee"] is None
