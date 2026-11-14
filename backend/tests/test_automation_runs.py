"""The run of an automation (plan M7 task 3, decision 3): its instruction is its
owner's turn, the only one it starts with; the instructions say a scheduled
automation of the owner asks. It answers at the top level of the owner's DM with the
agent, in a channel in a thread of its own per term (opened by a system entry
`automation.started` that names the automation, never its instruction), in a
ticket's thread at the top level after that entry. Nothing it leaves unanswered
gets a follow-up run, and a run taken up again after a lost worker asks with the
same instruction, whatever the owner edited meanwhile."""

import json
import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.modules.agents.executor_repository import claim
from app.modules.agents.models import Run, RunState, StopReason
from app.modules.messaging.models import MessageKind
from app.modules.tickets.models import WorkItem
from app.modules.tickets.thread_repository import TicketThreadRepository
from tests.factories_agents import LEASE, Bench
from tests.factories_automations import T0, fire, placed, runs_of
from tests.factories_tools import call
from tests.factories_writing import Work, events, messages_in
from tests.test_run_replay import Crash, die_after, take_up_again

ORDER = "Fasse die Tickets der Woche zusammen. GEHEIM-7"


def _chats(bench: Bench) -> list[dict[str, Any]]:
    return [r.body for r in bench.stub.state.log if r.path.endswith("/chat/completions")]


def _turns(body: dict[str, Any]) -> list[tuple[str, Any]]:
    return [(m["role"], m.get("content")) for m in body["messages"] if m["role"] != "system"]


def _system(body: dict[str, Any]) -> str:
    return str(next(m for m in body["messages"] if m["role"] == "system")["content"])


async def _channel(work: Work) -> uuid.UUID:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "bericht"})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


async def _no_order_outside(bench: Bench) -> None:
    for kind in ("message.created", "notification.created"):
        for event in await events(bench.session, kind):
            assert "GEHEIM" not in json.dumps(event.payload)


async def test_a_dm_automation_asks_with_its_instruction_alone(bench: Bench) -> None:
    await bench.say("Eine frühere Frage")
    bench.stub.state.replies.append({"content": "Frühere Antwort"})
    assert await bench.run_next() == StopReason.COMPLETED
    automation = await placed(bench, bench.dm_id, instruction=ORDER)
    await fire(bench)
    bench.stub.state.replies.append({"content": "Der Wochenbericht"})
    assert await bench.run_next() == StopReason.COMPLETED
    sent = _chats(bench)[-1]
    assert _turns(sent) == [("user", ORDER)]  # nothing earlier of the DM, no other turn
    system = _system(sent)
    alice = bench.people.users["alice"].name
    assert f'scheduled automation of "{alice}"' in system
    assert "in a direct conversation with one person." in system
    last = (await bench.messages())[-1]
    assert (last["body_md"], last["parent_id"], last["kind"]) == (
        "Der Wochenbericht",
        None,
        "agent",
    )
    assert not [m for m in await bench.messages() if m["kind"] == "system"]  # no entry in a DM
    [run] = await runs_of(bench.session, automation.id)
    assert (run.state, run.stop_reason) == (RunState.DONE, StopReason.COMPLETED)
    await _no_order_outside(bench)


async def test_a_channel_automation_opens_a_thread_per_term(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    automation = await placed(bench, channel, instruction=ORDER)
    for hour in range(2):
        await fire(bench, T0 + timedelta(hours=hour))
        bench.stub.state.replies.append({"content": f"Bericht {hour}"})
        assert await bench.run_next() == StopReason.COMPLETED
        sent = _chats(bench)[-1]
        assert _turns(sent) == [("user", ORDER)]
        alice = bench.people.users["alice"].name
        assert f'Only one person asks you: "{alice}' in _system(sent)
        assert f'scheduled automation of "{alice}"' in _system(sent)
    said = await messages_in(bench.session, channel)
    roots = [m for m in said if m.parent_id is None]
    assert [m.kind for m in roots] == [MessageKind.SYSTEM, MessageKind.SYSTEM]
    for hour, root in enumerate(roots):
        body = json.loads(root.body_md)
        assert body == {
            "key": "automation.started",
            "actor": str(bench.people.users["alice"].id),
            "automation_id": str(automation.id),
        }
        replies = [m for m in said if m.parent_id == root.id]
        assert [(m.kind, m.body_md) for m in replies] == [(MessageKind.AGENT, f"Bericht {hour}")]
        assert root.reply_count == 1
    r = await bench.people.alice.get(f"/api/conversations/{channel}/messages?limit=10")
    entries = [m["system"] for m in r.json()["items"] if m["system"]]
    assert {(e["key"], e["automation_id"], e["actor"]["name"]) for e in entries} == {
        ("automation.started", str(automation.id), bench.people.users["alice"].name)
    }
    await _no_order_outside(bench)


async def test_a_ticket_thread_automation_answers_at_the_top_level(work: Work) -> None:
    bench = work.bench
    made = await work.ticket()
    ticket = await bench.session.get(WorkItem, uuid.UUID(made["id"]))
    assert ticket is not None
    thread = await TicketThreadRepository(bench.session, ticket.org_id).thread_for(ticket)
    automation = await placed(bench, thread.id, instruction=ORDER)
    await fire(bench)
    bench.stub.state.replies.append({"content": "Stand des Tickets"})
    assert await bench.run_next() == StopReason.COMPLETED
    said = [m for m in await messages_in(bench.session, thread.id) if m.client_id is not None]
    started = [m for m in said if m.kind == MessageKind.SYSTEM and "automation" in m.body_md]
    assert len(started) == 1 and json.loads(started[0].body_md)["automation_id"] == str(
        automation.id
    )
    answer = next(m for m in said if m.kind == MessageKind.AGENT)
    assert (answer.parent_id, answer.body_md) == (None, "Stand des Tickets")


async def test_no_follow_up_run_after_an_automation_run(bench: Bench) -> None:
    """Alice writes in the DM while the automation's run works; the DM's own run
    answers her. The automation's run, ending, queues nothing for her message."""
    await placed(bench, bench.dm_id, instruction=ORDER)
    await fire(bench)
    async with bench.unit()() as session:
        working = await claim(session, LEASE)
    assert working is not None and working.automation_id is not None
    await bench.say("Und noch was")
    assert await bench.run_next() == StopReason.COMPLETED  # the DM's own run
    assert await bench.executor().execute(working) == StopReason.COMPLETED
    queued = await bench.session.scalars(select(Run).where(Run.state != RunState.DONE))
    assert list(queued) == []


async def test_a_run_taken_up_again_asks_with_the_same_instruction(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    automation = await placed(bench, bench.dm_id, instruction=ORDER)
    await fire(bench)
    bench.stub.state.replies.extend([call("search", query="Woche"), {"content": "Fertig"}])
    die_after(monkeypatch, "call_tool")
    with pytest.raises(Crash):
        await bench.run_next()
    monkeypatch.undo()
    automation.instruction = "Etwas ganz anderes"  # the owner edits meanwhile
    await bench.session.flush()
    assert await take_up_again(bench) == StopReason.COMPLETED
    first, second = _chats(bench)
    assert _turns(first) == [("user", ORDER)]
    assert _turns(second)[0] == ("user", ORDER)  # the same context, from the journal on
    assert len(_turns(second)) == 3  # the instruction, the replayed call, its result
    said = await bench.messages()
    assert said[-1]["body_md"] == "Fertig"
    assert len([m for m in said if m["kind"] == "agent"]) == 1
