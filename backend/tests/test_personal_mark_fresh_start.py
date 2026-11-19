"""Module review M8 3, H2: in her DM alone with the agent the personal mark lasts as
long as marked messages are in a run's history window, since a marked answer can
carry what she read. She ends it knowingly with "Neu beginnen" (start afresh): a
boundary on the DM (`conversation.fresh_start_at`); runs after it get no history from
before it (the window, `read_conversation`), so with nothing marked in their context
they start unmarked. Open runs of the DM are cancelled first. Only she, in her DM alone
with the agent, may set it; it is audited without content. Nothing is unflagged."""

from typing import Any

from sqlalchemy import select

from app.modules.agents.run_models import EventKind, Run, RunEvent, RunState, StopReason
from app.modules.audit.models import AuditLog
from tests.factories_dms import dm_of
from tests.factories_external import Ext, call
from tests.factories_personal import pending
from tests.factories_writing import Work
from tests.test_run_external_personal import SECRET, _personal

LONG = "lang " * 1_800  # 9,000 characters


async def _marked(ext: Ext) -> None:
    name = await _personal(ext)
    state = ext.bench.stub.state
    state.replies.extend([call(name, q="meine"), {"content": f"Da: {SECRET}"}])
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() == StopReason.COMPLETED


async def _fresh_start(ext: Ext, who: str = "alice", dm: str | None = None) -> Any:
    client = getattr(ext.bench.people, who)
    conversation = dm or ext.bench.dm_id
    found = await client.get(f"/api/conversations/{conversation}")
    version = found.json()["version"] if found.status_code == 200 else 1
    return await client.post(
        f"/api/conversations/{conversation}/fresh-start", json={"version": version}
    )


async def _ticket(ext: Ext, work: Work) -> StopReason | None:
    space = str(work.space.id)
    ext.bench.stub.state.replies.extend(
        [call("create_ticket", space_id=space, title="Drucker bestellen"), {"content": "Ok."}]
    )
    await ext.bench.say("Leg bitte ein Ticket an: Drucker bestellen")
    return await ext.bench.run_next()


async def test_without_a_fresh_start_the_mark_holds_in_a_dm_that_goes_on(
    ext: Ext, work: Work
) -> None:
    """The review's case, by design: every answer of a marked run is marked, so while
    one is in the window a later run is marked; a ticket waits for her release."""
    await _marked(ext)
    for _ in range(4):  # she writes at length and waits for each answer
        ext.bench.stub.state.replies.append({"content": "Ok."})
        await ext.bench.say(LONG)
        assert await ext.bench.run_next() == StopReason.COMPLETED
    assert await _ticket(ext, work) is None  # waits
    assert len(await pending(ext.bench.people.alice)) == 1


async def test_after_a_fresh_start_the_mark_ends(ext: Ext, work: Work) -> None:
    await _marked(ext)
    r = await _fresh_start(ext)
    assert r.status_code == 200, r.text
    assert r.json()["fresh_start_at"] is not None
    assert await _ticket(ext, work) == StopReason.COMPLETED  # carried out, no release
    assert await pending(ext.bench.people.alice) == []
    body = str(ext.bench.stub.state.log[-1].body)
    assert SECRET not in body and "Such meine Issues" not in body  # nothing from before
    answers = [m for m in await ext.bench.messages() if m["kind"] == "agent"]
    assert [m["personal"] for m in answers] == [True, False]  # the old one stays marked
    run = await ext.bench.session.scalar(select(Run).order_by(Run.created_at.desc()))
    assert run is not None
    marks = await ext.bench.session.scalars(
        select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.kind == EventKind.MARK)
    )
    assert list(marks) == []


async def test_read_conversation_reads_nothing_from_before(ext: Ext) -> None:
    await _marked(ext)
    assert (await _fresh_start(ext)).status_code == 200
    state = ext.bench.stub.state
    state.replies.extend([call("read_conversation"), {"content": "Nichts davor."}])
    await ext.bench.say("Was stand vorher hier?")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    (read,) = [e for e in await ext.tool_events() if e["name"] == "read_conversation"]
    assert SECRET not in read["text"] and "(personal)" not in read["text"]
    assert "personal" not in read["read"]
    assert "Was stand vorher hier?" in read["text"]


async def test_open_runs_of_the_dm_are_cancelled(ext: Ext) -> None:
    await ext.bench.say("Noch offen")  # queued, nobody took it yet
    assert (await _fresh_start(ext)).status_code == 200
    run = await ext.bench.session.scalar(select(Run))
    assert run is not None and run.state == RunState.DONE
    assert run.stop_reason == StopReason.CANCELLED


async def test_it_is_audited_without_content(ext: Ext) -> None:
    await _marked(ext)
    assert (await _fresh_start(ext)).status_code == 200
    entry = await ext.bench.session.scalar(
        select(AuditLog).where(AuditLog.action == "conversation.fresh_start")
    )
    assert entry is not None and str(entry.target_id) == ext.bench.dm_id
    assert set(entry.details or {}) <= {"cancelled_runs"}
    assert SECRET not in str(entry.details)


async def test_only_she_in_her_dm_alone_with_the_agent_may(ext: Ext, work: Work) -> None:
    people = ext.bench.people
    assert (await _fresh_start(ext, "bob")).status_code == 404  # not hers: unknown
    with_bob = await dm_of(people.alice, people.users["bob"].id)
    r = await _fresh_start(ext, "alice", with_bob["id"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "conversation.not_alone_with_agent"
    channel = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "k"})
    r = await _fresh_start(ext, "admin", channel.json()["id"])
    assert r.status_code == 403
    stale = await people.alice.post(
        f"/api/conversations/{ext.bench.dm_id}/fresh-start", json={"version": 999}
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "conversation.version_conflict"
