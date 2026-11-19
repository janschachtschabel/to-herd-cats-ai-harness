"""A run from the message to the answer (plan M5 task 6), against the OpenAI stub:
the answer once (`client_id` = the run), the steps and their usage once, later
messages waiting for one run that answers them together, and the stop notice."""

import json
import uuid

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import func, select

from app.core.outbox import Event, EventOutbox
from app.modules.agents.executor_repository import claim
from app.modules.agents.run_models import EventKind, Run, RunEvent, RunState, StopReason
from app.modules.ai.models import UsageRecord
from app.modules.messaging.live_decode import decode
from app.modules.messaging.live_publish import of_event
from app.modules.messaging.models import Message
from app.runtime.models import wrap_model
from tests.factories_agents import Bench


async def test_a_message_gets_one_answer(bench: Bench) -> None:
    bench.stub.state.replies.append({"content": "Hello Alice."})
    posted = await bench.say("Hi Ava")
    run_id = posted["agent_run"]["id"]
    assert posted["agent_run"]["reason"] is None
    assert await bench.run_next() == StopReason.COMPLETED
    run = await bench.run_of(run_id)
    assert (run.state, run.stop_reason, run.steps, run.attempt) == ("done", "completed", 1, 1)
    answers = [m for m in await bench.messages() if m["kind"] == "agent"]
    assert len(answers) == 1
    assert answers[0]["body_md"] == "Hello Alice."
    assert answers[0]["client_id"] == run_id
    assert answers[0]["author"]["type"] == "agent"
    assert answers[0]["author"]["id"] == str(bench.agent.id)
    assert answers[0]["author"]["name"] == "Ava"
    sent = bench.stub.state.log[-1].body
    assert sent["model"] == "m1" and sent["max_tokens"] == 4096
    assert "Hi Ava" in json.dumps(sent["messages"])
    assert "Be brief." in json.dumps(sent["messages"])  # the agent's instructions
    usage = (await bench.session.scalars(select(UsageRecord))).all()
    assert [(u.run_id, u.agent_id, u.user_id) for u in usage] == [
        (run.id, bench.agent.id, bench.people.users["alice"].id)
    ]
    kinds = (
        await bench.session.scalars(
            select(RunEvent.kind).where(RunEvent.run_id == run.id).order_by(RunEvent.seq)
        )
    ).all()
    assert kinds == [EventKind.STOP, EventKind.MODEL_CALL]


async def test_messages_while_a_run_waits_share_it(bench: Bench) -> None:
    first = await bench.say("One")
    second = await bench.say("Two")
    assert first["agent_run"]["id"] == second["agent_run"]["id"]
    bench.stub.state.replies.append({"content": "Both answered."})
    assert await bench.run_next() == StopReason.COMPLETED
    sent = json.dumps(bench.stub.state.log[-1].body["messages"])
    assert "One" in sent and "Two" in sent
    count = await bench.session.scalar(select(func.count()).select_from(Run))
    assert count == 1


async def test_a_message_during_a_run_queues_the_next(bench: Bench) -> None:
    await bench.say("First question")
    async with bench.unit()() as session:
        claimed = await claim(session, 30)
    assert claimed is not None
    later = await bench.say("Second question")  # while the first run works
    assert later["agent_run"]["id"] != str(claimed.id)
    bench.stub.state.replies.extend([{"content": "Answer one."}, {"content": "Answer two."}])
    assert await bench.executor().execute(claimed) == StopReason.COMPLETED
    first = json.dumps(bench.stub.state.log[0].body["messages"])
    assert "Second question" not in first  # written after the run started
    run = await bench.run_of(later["agent_run"]["id"])
    assert run.state == RunState.QUEUED
    assert await bench.run_next() == StopReason.COMPLETED
    sent = [m.get("content") for m in bench.stub.state.log[1].body["messages"]]
    order = [sent.index(t) for t in ("First question", "Answer one.", "Second question")]
    assert order == sorted(order)  # the answer before the message sent while it worked
    bodies = [m["body_md"] for m in await bench.messages()]
    assert bodies.count("Answer one.") == 1 and bodies.count("Answer two.") == 1


async def test_a_stop_leaves_a_notice(bench: Bench) -> None:
    bench.stub.state.failures.append(401)
    await bench.say("Hi")
    assert await bench.run_next() == StopReason.PROVIDER_REFUSED
    notices = [m for m in await bench.messages() if m["kind"] == "system"]
    assert len(notices) == 1
    assert notices[0]["system"]["key"] == "run.stopped"
    assert notices[0]["system"]["new"]["value"] == "provider_refused"
    assert notices[0]["body_md"] == ""
    assert len(bench.stub.state.log) == 1  # no retry


async def test_progress_goes_live_with_ids_and_the_step_only(bench: Bench) -> None:
    bench.stub.state.replies.extend(
        [{"tool_calls": [{"name": "search", "arguments": {"query": "x"}}]}, {"content": "ok"}]
    )
    posted = await bench.say("Secret question")
    assert await bench.run_next() == StopReason.COMPLETED
    rows = (
        await bench.session.scalars(
            select(EventOutbox).where(EventOutbox.type == "run.progress").order_by(EventOutbox.id)
        )
    ).all()
    assert [r.payload["step"] for r in rows] == [1, 2]
    event = of_event(Event.of(rows[-1]))
    assert event is not None
    assert (event.conversation_id, event.run_id, event.step) == (
        uuid.UUID(bench.dm_id),
        uuid.UUID(posted["agent_run"]["id"]),
        2,
    )
    payload = event.payload()
    assert decode(payload) == event
    assert "Secret" not in payload and "Secret" not in event.frame().decode()
    assert b'"step":2' in event.frame()
    assert decode(payload.replace('"k":2', '"k":"2"')) is None


async def test_a_run_whose_question_was_deleted_sends_nothing(bench: Bench) -> None:
    """Finding 10: no person's message left to answer → no call, no answer, no notice."""
    bench.stub.state.replies.append({"content": "Answer one."})
    await bench.say("First question")
    assert await bench.run_next() == StopReason.COMPLETED
    for text in ("Never mind", None):
        if text is None:  # the very first message of a DM, deleted
            await bench.session.execute(Message.__table__.update().values(deleted_at=func.now()))
        posted = await bench.say(text or "Again")
        r = await bench.people.alice.delete(f"/api/messages/{posted['id']}")
        assert r.status_code == 204, r.text
        assert await bench.run_next() == StopReason.COMPLETED
    assert len(bench.stub.state.log) == 1
    kinds = [m["kind"] for m in await bench.messages()]
    assert kinds.count("agent") <= 1 and "system" not in kinds


async def test_usage_names_the_model_the_call_went_to(bench: Bench) -> None:
    """Finding 13: an edit of the agent during the run does not move its usage."""
    bench.connection.models = ["m1", "m2"]
    await bench.session.flush()
    calls: list[int] = []

    async def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        if len(calls) == 1:
            bench.agent.model = "m2"
            await bench.session.flush()
            return ModelResponse(parts=[ToolCallPart("search", {"query": "x"})])
        return ModelResponse(parts=[TextPart("done")])

    executor = bench.executor(make_model=lambda target, timeout: wrap_model(FunctionModel(model)))
    await bench.say("Hi")
    assert await bench.run_next(executor) == StopReason.COMPLETED
    models = (await bench.session.scalars(select(UsageRecord.model))).all()
    assert models == ["m1", "m1"]


async def test_usage_per_agent_names_the_agent(bench: Bench) -> None:
    """Finding 12: `by=agent` gives the agent's name."""
    bench.stub.state.replies.append({"content": "Hi."})
    await bench.say("Hi")
    assert await bench.run_next() == StopReason.COMPLETED
    rows = (await bench.people.admin.get("/api/ai/usage", params={"by": "agent"})).json()
    assert [(r["key_id"], r["name"], r["calls"]) for r in rows["items"]] == [
        (str(bench.agent.id), "Ava", 1)
    ]
