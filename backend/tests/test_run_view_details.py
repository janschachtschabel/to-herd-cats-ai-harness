"""The run view in detail (plan M6 task 10): a run's place names its space, page or
ticket only to a reader who reads that space; its events carry their tokens, cost and
duration where the step recorded them, also when the rest is redacted."""

import uuid
from decimal import Decimal

from app.core.models_base import utcnow
from app.core.permissions import SpaceRole
from app.modules.agents.models import StopReason
from app.modules.agents.run_repository import RunRepository
from app.modules.messaging.models import Conversation, Message, MessageKind
from app.modules.spaces.models import SpaceKind
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import new_ticket
from tests.test_run_view import RUNS, listed


async def test_the_place_of_a_run_hides_a_space_the_reader_does_not_see(
    bench: Bench, make_space: MakeSpace
) -> None:
    users = bench.people.users
    space = await make_space(SpaceKind.TEAM, members=[(users["alice"], SpaceRole.EDITOR)])
    channel = Conversation(org_id=space.org_id, kind="channel", space_id=space.id, name="k")
    bench.session.add(channel)
    await bench.session.flush()
    said = Message(
        org_id=space.org_id,
        conversation_id=channel.id,
        author_type="user",
        author_id=users["alice"].id,
        kind=MessageKind.HUMAN,
        body_md="@Ava?",
        created_at=utcnow(),
    )
    bench.session.add(said)
    await bench.session.flush()
    run_id = await RunRepository(bench.session, space.org_id).enqueue(
        bench.agent.id, users["alice"].id, channel.id, said.id
    )
    bench.agent.responsible_user_id = users["bob"].id
    await bench.session.flush()
    own = (await bench.people.alice.get(f"{RUNS}/{run_id}")).json()["place"]
    assert own == {
        "kind": "channel",
        "conversation_id": str(channel.id),
        "space_id": str(space.id),
        "page_id": None,
        "ticket_number": None,
    }
    hidden = (await bench.people.bob.get(f"{RUNS}/{run_id}")).json()["place"]
    assert hidden["kind"] == "channel" and hidden["space_id"] is None
    shown = await listed(bench.people.bob, f"/api/agents/{bench.agent.id}/runs")
    assert shown[0]["place"]["space_id"] is None
    admin = (await bench.people.admin.get(f"{RUNS}/{run_id}")).json()["place"]
    assert admin["space_id"] == str(space.id)


async def test_events_carry_their_cost_tokens_and_duration(bench: Bench) -> None:
    bench.connection.prices = {"m1": {"input": "1", "output": "2"}}
    await bench.session.flush()
    bench.stub.state.replies.extend(
        [{"tool_calls": [{"name": "search", "arguments": {"query": "x"}}]}, {"content": "Ok."}]
    )
    run_id = (await bench.say("Find"))["agent_run"]["id"]
    assert await bench.run_next() == StopReason.COMPLETED
    bench.agent.responsible_user_id = bench.people.users["bob"].id
    await bench.session.flush()
    for who in ("alice", "bob"):  # the asker, and a reader who gets it redacted
        r = await getattr(bench.people, who).get(f"{RUNS}/{run_id}/events")
        items = r.json()["items"]
        models = [e for e in items if e["kind"] == "model_call"]
        assert len(models) == 2
        for e in models:
            assert e["tokens_in"] > 0 and e["tokens_out"] > 0 and e["tokens_cached"] == 0
            assert float(e["cost"]) > 0 and e["duration_ms"] >= 0
        tool = next(e for e in items if e["kind"] == "tool_call")
        assert tool["duration_ms"] >= 0 and tool["cost"] is None and tool["tokens_in"] is None
        stop = next(e for e in items if e["kind"] == "stop")
        assert (stop["cost"], stop["duration_ms"]) == (None, None)
    total = (await bench.people.alice.get(f"{RUNS}/{run_id}")).json()["usage"]
    assert total["calls"] == 2
    assert sum(Decimal(e["cost"]) for e in models) == Decimal(total["cost"])


async def test_a_ticket_threads_run_names_its_ticket_where_the_reader_sees_it(
    bench: Bench, make_space: MakeSpace
) -> None:
    users = bench.people.users
    space = await make_space(SpaceKind.TEAM, members=[(users["alice"], SpaceRole.EDITOR)])
    ticket = await new_ticket(bench.people.alice, space.id, "Fix it")
    thread = await bench.people.alice.get(f"/api/tickets/{ticket['number']}/thread")
    assert thread.status_code == 200, thread.text
    said = await bench.people.alice.post(
        f"/api/conversations/{thread.json()['id']}/messages", json={"body_md": "Please"}
    )
    assert said.status_code == 201, said.text
    run_id = await RunRepository(bench.session, space.org_id).enqueue(
        bench.agent.id, users["alice"].id, uuid.UUID(thread.json()["id"]), said.json()["id"]
    )
    bench.agent.responsible_user_id = users["bob"].id
    await bench.session.flush()
    own = (await bench.people.alice.get(f"{RUNS}/{run_id}")).json()["place"]
    assert (own["kind"], own["space_id"], own["ticket_number"]) == (
        "thread_ticket",
        str(space.id),
        ticket["number"],
    )
    hidden = (await bench.people.bob.get(f"{RUNS}/{run_id}")).json()["place"]
    assert (hidden["space_id"], hidden["ticket_number"], hidden["page_id"]) == (None, None, None)
