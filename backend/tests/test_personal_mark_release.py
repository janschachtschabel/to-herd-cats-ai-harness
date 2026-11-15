"""Module review M8 2, finding G2: the personal mark no longer ends writing for good.

- It ends when no personal content is in a run's context: a run whose history window
  holds no marked message starts unmarked and writes as any other.
- Under the mark, a write others could read waits for the asking person's release,
  which shows exactly what would be written; what is written then is not marked (she
  decided to publish it), and the run stays marked for whatever it writes next.
- The draft mark is unchanged: it refuses, release or not."""

import pytest
from sqlalchemy import select

from app.modules.agents.run_models import EventKind, RunEvent, StopReason
from app.modules.agents.toolbox.writing import DRAFTS
from app.modules.messaging.models import Message
from tests.factories_external import Ext, call
from tests.factories_personal import asks_release, decide, pending
from tests.factories_writing import Work
from tests.test_drafts_every_write_tool import REFUSED, _after_a_draft
from tests.test_run_external_personal import SECRET, _channel, _personal

LONG = "lang " * 1_800  # 9,000 characters: three of them push anything out of the window


async def _read_in_her_dm(ext: Ext) -> None:
    name = await _personal(ext)
    ext.bench.stub.state.replies.extend([call(name, q="meine"), {"content": f"Da: {SECRET}"}])
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() == StopReason.COMPLETED


async def _in(ext: Ext, conversation_id: str) -> list[Message]:
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    return list(await ext.bench.session.scalars(stmt))


async def test_the_mark_ends_once_marked_messages_leave_the_window(ext: Ext, work: Work) -> None:
    """The review's case, to the ruling: after one personal read, ordinary work in her
    DM goes on without a release once the marked answer is out of the window."""
    await _read_in_her_dm(ext)
    state = ext.bench.stub.state
    space = str(work.space.id)
    state.replies.extend(
        [call("create_ticket", space_id=space, title="Drucker bestellen"), {"content": "Ok."}]
    )
    for _ in range(3):
        await ext.bench.say(LONG)
    await ext.bench.say("Leg bitte ein Ticket an: Drucker bestellen")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert SECRET not in str(state.log[-2].body)  # the run never saw the personal words
    created = [e for e in await ext.tool_events() if e["name"] == "create_ticket"][-1]
    assert created["text"].startswith("Created"), created["text"]
    marks = list(
        await ext.bench.session.scalars(select(RunEvent).where(RunEvent.kind == EventKind.MARK))
    )
    assert marks == []
    answers = [m for m in await ext.bench.messages() if m["kind"] == "agent"]
    assert [m["personal"] for m in answers] == [True, False]  # the first read, the last not
    assert await pending(ext.bench.people.alice) == []


async def test_a_release_writes_exactly_what_was_shown_unmarked(ext: Ext, work: Work) -> None:
    channel = await _channel(work)
    await _read_in_her_dm(ext)
    text = f"Für alle: {SECRET}"
    ext.bench.stub.state.replies.extend(
        [call("post_message", conversation_id=channel, text=text), {"content": "Erledigt."}]
    )
    await ext.bench.say("Schreib das dem Team")
    approval = await asks_release(ext, await ext.bench.run_next())
    assert approval["tool"] == "post_message" and approval["args"]["text"] == text
    (card,) = [m for m in await ext.bench.messages() if m["kind"] == "approval"]
    assert card["personal"] is False and SECRET not in card["body_md"]  # names, no content
    assert await _in(ext, channel) == []
    await decide(ext, approval, "approve")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    (posted,) = await _in(ext, channel)
    assert posted.body_md == text and posted.personal is False and posted.kind == "agent"
    shown = (await ext.bench.people.alice.get(f"/api/approvals/{approval['id']}")).json()
    assert shown["outcome"] == "ran"
    final = [m for m in await ext.bench.messages() if m["body_md"] == "Erledigt."]
    assert [m["personal"] for m in final] == [True]  # alone with her it stays marked


async def test_after_a_release_the_run_still_carries_the_mark(ext: Ext, work: Work) -> None:
    """A resume after a release replays the mark: the next write asks again."""
    channel = await _channel(work)
    await _read_in_her_dm(ext)
    ext.bench.stub.state.replies.extend(
        [
            call("post_message", conversation_id=channel, text="Erstens"),
            call("post_message", conversation_id=channel, text=f"Zweitens: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Schreib das dem Team")
    first = await asks_release(ext, await ext.bench.run_next())
    await decide(ext, first, "approve")
    second = await asks_release(ext, await ext.bench.run_next())
    assert second["id"] != first["id"] and second["args"]["text"] == f"Zweitens: {SECRET}"
    assert [m.body_md for m in await _in(ext, channel)] == ["Erstens"]
    await decide(ext, second, "reject")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert [m.body_md for m in await _in(ext, channel)] == ["Erstens"]


async def test_a_rejection_writes_nothing_and_the_model_learns_it(ext: Ext, work: Work) -> None:
    channel = await _channel(work)
    await _read_in_her_dm(ext)
    ext.bench.stub.state.replies.extend(
        [
            call("post_message", conversation_id=channel, text=f"Für alle: {SECRET}"),
            {"content": "Gut, dann nicht."},
        ]
    )
    await ext.bench.say("Schreib das dem Team")
    approval = await asks_release(ext, await ext.bench.run_next())
    await decide(ext, approval, "reject")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert await _in(ext, channel) == []
    assert "approval_rejected" in ext.bench.stub.state.texts()


@pytest.mark.parametrize("name", sorted(REFUSED))
async def test_the_draft_mark_still_refuses_under_the_personal_mark(work: Work, name: str) -> None:
    ctx = await _after_a_draft(work)
    ctx.reads.personal = True
    assert await REFUSED[name](work, ctx) == DRAFTS  # no release asked: refused
