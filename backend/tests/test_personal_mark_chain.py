"""Module review M8 2, finding G1: the personal mark follows the content and is
persisted. A run is marked the moment personal content enters its context (its
history window, `search_past_runs`, `read_conversation`), and that moment is in its
journal, so the mark survives every take-up; every message a marked run writes is
marked (`message.personal`), so the next run's history carries it on, through any
number of runs. (Before: the mark a run inherited lived only in its worker's memory,
so one run further on the personal words left again.)"""

from typing import Any

import pytest
from sqlalchemy import select

from app.modules.agents.personal_mark import PRESENT
from app.modules.agents.run_models import EventKind, Run, RunEvent, StopReason
from app.modules.agents.toolbox.writing import PERSONAL
from app.modules.messaging.models import Message
from tests.factories_external import Ext, call
from tests.factories_writing import Work
from tests.test_questions import answer
from tests.test_run_external_personal import SECRET, _channel, _personal
from tests.test_run_replay import Crash, die_after, take_up_again

LONG = "lang " * 1_800  # 9,000 characters: three of them push anything out of the window


async def _bodies(ext: Ext) -> list[str]:
    return list(await ext.bench.session.scalars(select(Message.body_md)))


async def _posted(ext: Ext) -> dict[str, Any]:
    return [e for e in await ext.tool_events() if e["name"] == "post_message"][-1]


async def _marks(ext: Ext) -> list[RunEvent]:
    stmt = select(RunEvent).where(RunEvent.kind == EventKind.MARK).order_by(RunEvent.seq)
    return list(await ext.bench.session.scalars(stmt))


async def _read_in_her_dm(ext: Ext, name: str) -> None:
    ext.bench.stub.state.replies.extend([call(name, q="meine"), {"content": f"Da: {SECRET}"}])
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() == StopReason.COMPLETED


async def test_the_mark_survives_a_run_that_only_inherited_it(ext: Ext, work: Work) -> None:
    """The review's proof: channel (held back), her DM (found by search, said there),
    the next run in her DM (history) tries to post it into the channel."""
    channel = await _channel(work)
    name = await _personal(ext)
    alice, state = ext.bench.people.alice, ext.bench.stub.state
    state.replies.extend([call(name, q="meine"), {"content": f"Da: {SECRET}"}])
    body = {"body_md": "@Ava such meine Issues", "mentions": [str(ext.bench.agent.id)]}
    r = await alice.post(f"/api/conversations/{channel}/messages", json=body)
    assert r.status_code == 201, r.text
    assert await ext.bench.run_next() == StopReason.POLICY_BLOCKED
    state.replies.extend([call("search_past_runs", query="Da:"), {"content": f"Es war: {SECRET}"}])
    await ext.bench.say("Was hattest du gefunden?")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    said = [m for m in await ext.bench.messages() if m["body_md"] == f"Es war: {SECRET}"]
    assert [m["personal"] for m in said] == [True]
    searched = [e for e in await ext.tool_events() if e["name"] == "search_past_runs"][-1]
    assert searched["read"]["personal"] is True  # journaled with the hit
    assert "(personal) " in searched["text"]
    state.replies.extend(
        [
            call("post_message", conversation_id=channel, text=f"Für alle: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Schreib das dem Team")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert SECRET in str(state.log[-1].body)  # the model did see it in the history
    assert PRESENT in str(state.log[-1].body)  # and was told it is hers
    assert f"Für alle: {SECRET}" not in await _bodies(ext)
    assert (await _posted(ext))["text"] == PERSONAL


async def test_a_run_marked_by_its_search_keeps_the_mark_when_taken_up_again(
    ext: Ext, work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    channel = await _channel(work)
    name = await _personal(ext)
    alice, state = ext.bench.people.alice, ext.bench.stub.state
    state.replies.extend([call(name, q="meine"), {"content": f"Da: {SECRET}"}])
    body = {"body_md": "@Ava such meine Issues", "mentions": [str(ext.bench.agent.id)]}
    r = await alice.post(f"/api/conversations/{channel}/messages", json=body)
    assert r.status_code == 201, r.text
    assert await ext.bench.run_next() == StopReason.POLICY_BLOCKED
    state.replies.extend(
        [
            call("search_past_runs", query="Da:"),
            call("post_message", conversation_id=channel, text=f"Für alle: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Was hattest du gefunden?")
    die_after(monkeypatch, "call_tool")  # the search's result is recorded, the worker dies
    with pytest.raises(Crash):
        await ext.bench.run_next()
    monkeypatch.undo()
    assert await take_up_again(ext.bench) == StopReason.COMPLETED
    assert f"Für alle: {SECRET}" not in await _bodies(ext)
    assert (await _posted(ext))["text"] == PERSONAL


async def test_the_chain_holds_over_several_runs_in_her_dm(ext: Ext, work: Work) -> None:
    channel = await _channel(work)
    await _read_in_her_dm(ext, await _personal(ext))
    state = ext.bench.stub.state
    for n in range(3):  # each run reads the marked answers before it, and is marked
        state.replies.append({"content": f"Antwort {n}"})
        await ext.bench.say(f"Frage {n}")
        assert await ext.bench.run_next() == StopReason.COMPLETED
    state.replies.extend(
        [
            call("post_message", conversation_id=channel, text=f"Für alle: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Schreib das dem Team")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert (await _posted(ext))["text"] == PERSONAL
    assert f"Für alle: {SECRET}" not in await _bodies(ext)
    answers = [m for m in await ext.bench.messages() if m["kind"] == "agent"]
    assert len(answers) == 5 and all(m["personal"] for m in answers)
    asked = [m for m in await ext.bench.messages() if m["kind"] == "human"]
    assert not any(m["personal"] for m in asked)  # her own words are hers to share
    marks = await _marks(ext)  # one per run that the history marked, none for the first
    assert len(marks) == 4 and len({m.run_id for m in marks}) == 4
    assert marks[0].content == {"read": {"personal": True}, "source": "conversation"}


async def test_a_resume_after_a_question_keeps_the_mark(ext: Ext, work: Work) -> None:
    channel = await _channel(work)
    await _read_in_her_dm(ext, await _personal(ext))
    state = ext.bench.stub.state
    state.replies.extend(
        [
            call("ask_user", question="An welchen Kanal?"),
            call("post_message", conversation_id=channel, text=f"Für alle: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Schreib das dem Team")
    assert await ext.bench.run_next() is None  # waits for her answer
    (card,) = [m for m in await ext.bench.messages() if m["kind"] == "question"]
    assert card["personal"] is True  # a marked run's question
    question = (await ext.bench.people.alice.get(f"/api/questions/{card['card']['id']}")).json()
    r = await answer(ext.bench, question, "werkbank")
    assert r.status_code == 200, r.text
    assert await ext.bench.run_next() == StopReason.COMPLETED  # a new take-up's memory
    assert (await _posted(ext))["text"] == PERSONAL
    assert f"Für alle: {SECRET}" not in await _bodies(ext)
    assert len(await _marks(ext)) == 1  # journaled once, replayed after the resume


async def test_a_run_marked_by_its_history_keeps_the_mark_when_taken_up_again(
    ext: Ext, work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    channel = await _channel(work)
    await _read_in_her_dm(ext, await _personal(ext))
    ext.bench.stub.state.replies.extend(
        [
            call("post_message", conversation_id=channel, text=f"Für alle: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Schreib das dem Team")
    die_after(monkeypatch, "after_model_call")  # the model's call is recorded, then it dies
    with pytest.raises(Crash):
        await ext.bench.run_next()
    monkeypatch.undo()
    assert len(await _marks(ext)) == 1  # journaled before the first model call
    assert await take_up_again(ext.bench) == StopReason.COMPLETED
    assert (await _posted(ext))["text"] == PERSONAL
    assert len(await _marks(ext)) == 1  # the take-up replayed it, wrote none anew


async def test_read_conversation_marks_the_run_with_what_it_returns(ext: Ext, work: Work) -> None:
    """The marked answer is out of the window (three long messages of hers after it),
    so the run starts unmarked; reading the conversation brings it back, and marks it."""
    channel = await _channel(work)
    await _read_in_her_dm(ext, await _personal(ext))
    state = ext.bench.stub.state
    state.replies.extend(
        [
            call("read_conversation"),
            call("post_message", conversation_id=channel, text=f"Für alle: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    for _ in range(3):
        await ext.bench.say(LONG)
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert SECRET not in str(state.log[-3].body)  # not in its window
    run = (await ext.bench.session.scalars(select(Run).order_by(Run.created_at.desc()))).first()
    assert run is not None
    assert not [m for m in await _marks(ext) if m.run_id == run.id]
    read = [e for e in await ext.tool_events() if e["name"] == "read_conversation"][-1]
    assert read["read"]["personal"] is True and "(personal) id=" in read["text"]
    assert (await _posted(ext))["text"] == PERSONAL
    assert f"Für alle: {SECRET}" not in await _bodies(ext)
