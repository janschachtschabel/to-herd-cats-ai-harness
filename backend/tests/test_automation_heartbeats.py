"""Heartbeats (plan M7 decision 7): a checklist the agent goes through every interval
inside the active hours. An answer of exactly `HEARTBEAT_OK` (after trimming) is
delivered nowhere: no message, no thread, no activity, no notification, no live
message event; the term's row in the log notes it. Any other answer, and any other
end, is delivered like an automation's answer (in a channel, in a thread its term
opens only then). Outside the active hours no term comes; a term the due loop takes
up long after the window closed (an outage) is skipped (`skipped_off_hours`)."""

import json
import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.core.outbox import Event, EventOutbox
from app.modules.agents.models import RunState, StopReason
from app.modules.automations.models import FiringOutcome
from app.modules.automations.repository import AutomationRepository
from app.modules.messaging.live_events import of_event
from app.modules.messaging.models import MessageKind
from app.modules.messaging.notification_models import Notification
from tests.factories_agents import Bench
from tests.factories_automations import (
    T0,
    beating,
    finish_runs,
    fire,
    firings,
    reload,
    runs_of,
)
from tests.factories_tools import call
from tests.factories_writing import Work, messages_in
from tests.test_approvals import NEW, confirm, decide
from tests.test_run_replay import Crash, die_after, take_up_again

CHECKLIST = "Prüfe offene Tickets. CHECK-91"
TOMORROW_NINE = T0 + timedelta(days=1, hours=-1)  # Tuesday 09:00 in Berlin


async def _channel(work: Work) -> uuid.UUID:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "puls"})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


def _system(bench: Bench) -> str:
    body = next(r.body for r in reversed(bench.stub.state.log) if r.path.endswith("/completions"))
    return str(next(m for m in body["messages"] if m["role"] == "system")["content"])


async def _traces(bench: Bench, since: Any) -> list[str]:
    """Events since the firing that tell anyone about a message or an activity."""
    rows = await bench.session.scalars(select(EventOutbox).where(EventOutbox.id > since))
    found = []
    for event in rows:
        payload = json.dumps(event.payload)
        if event.type.startswith(("message.", "notification.")) or "message_id" in payload:
            found.append(event.type)
    return found


async def _last_event_id(bench: Bench) -> Any:
    last = select(EventOutbox.id).order_by(EventOutbox.id.desc()).limit(1)
    return await bench.session.scalar(last) or uuid.UUID(int=0)


async def test_a_heartbeat_fires_in_its_hours_and_takes_the_next_term(bench: Bench) -> None:
    automation = await beating(bench, bench.dm_id, every=45, checklist=CHECKLIST)
    fired = await fire(bench)
    assert fired.outcome == FiringOutcome.STARTED
    [logged] = await firings(bench.session, automation.id)
    assert (logged.instruction, logged.heartbeat_ok) == (CHECKLIST, False)
    after = await reload(bench.session, automation.id)
    assert after.next_due_at == T0 + timedelta(minutes=45)
    late = T0.replace(hour=15, minute=50)  # 16:50 in Berlin: the next term is tomorrow 09:00
    after.next_due_at = late
    await bench.session.flush()
    await finish_runs(bench.session)
    await fire(bench, late)
    assert (await reload(bench.session, automation.id)).next_due_at == TOMORROW_NINE


async def test_heartbeat_ok_leaves_no_trace_but_the_log(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    automation = await beating(bench, channel, checklist=CHECKLIST)
    since = await _last_event_id(bench)
    await fire(bench)
    assert await messages_in(bench.session, channel) == []  # no thread before an answer
    bench.stub.state.replies.append({"content": "  HEARTBEAT_OK\n"})
    assert await bench.run_next() == StopReason.COMPLETED
    assert "HEARTBEAT_OK" in _system(bench)  # the frame tells the model the rule
    assert await messages_in(bench.session, channel) == []
    assert list(await bench.session.scalars(select(Notification.id))) == []
    assert await _traces(bench, since) == []
    [logged] = await firings(bench.session, automation.id)
    assert (logged.outcome, logged.heartbeat_ok) == (FiringOutcome.STARTED, True)
    page = await AutomationRepository(bench.session, automation.org_id).log_page(
        automation.id, None, 10
    )
    assert [(f.id, f.heartbeat_ok) for f in page] == [(logged.id, True)]
    [run] = await runs_of(bench.session, automation.id)
    assert (run.state, run.stop_reason) == (RunState.DONE, StopReason.COMPLETED)
    assert (await reload(bench.session, automation.id)).failures == 0


async def test_heartbeat_ok_in_a_dm_posts_nothing(bench: Bench) -> None:
    automation = await beating(bench, bench.dm_id)
    await fire(bench)
    bench.stub.state.replies.append({"content": "HEARTBEAT_OK"})
    assert await bench.run_next() == StopReason.COMPLETED
    assert await bench.messages() == []
    [logged] = await firings(bench.session, automation.id)
    assert logged.heartbeat_ok


async def test_anything_else_is_delivered_in_a_thread_opened_then(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    automation = await beating(bench, channel)
    await fire(bench)
    bench.stub.state.replies.append({"content": "HEARTBEAT_OK, aber HC-3 liegt seit Tagen"})
    assert await bench.run_next() == StopReason.COMPLETED
    said = await messages_in(bench.session, channel)
    (root,) = [m for m in said if m.parent_id is None]
    assert root.kind == MessageKind.SYSTEM
    assert json.loads(root.body_md)["automation_id"] == str(automation.id)
    (reply,) = [m for m in said if m.parent_id == root.id]
    assert reply.body_md == "HEARTBEAT_OK, aber HC-3 liegt seit Tagen"
    assert root.reply_count == 1
    [logged] = await firings(bench.session, automation.id)
    assert logged.heartbeat_ok is False


async def test_a_failed_heartbeat_tells_in_a_thread_of_its_own(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    await beating(bench, channel)
    await fire(bench)
    bench.stub.state.failures.append(401)
    assert await bench.run_next() == StopReason.PROVIDER_REFUSED
    said = await messages_in(bench.session, channel)
    (root,) = [m for m in said if m.parent_id is None]
    (notice,) = [m for m in said if m.parent_id == root.id]
    assert json.loads(notice.body_md)["to"] == "provider_refused"


async def test_a_heartbeat_taken_up_again_stays_silent(
    work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench, channel = work.bench, await _channel(work)
    automation = await beating(bench, channel)
    await fire(bench)
    bench.stub.state.replies.append({"content": "HEARTBEAT_OK"})
    die_after(monkeypatch, "after_model_call")
    with pytest.raises(Crash):
        await bench.run_next()
    monkeypatch.undo()
    calls = len(bench.stub.state.log)
    assert await take_up_again(bench) == StopReason.COMPLETED
    assert len(bench.stub.state.log) == calls  # the reply came from the journal
    assert await messages_in(bench.session, channel) == []
    [logged] = await firings(bench.session, automation.id)
    assert logged.heartbeat_ok


async def test_a_term_taken_up_after_its_window_closed_is_skipped(bench: Bench) -> None:
    automation = await beating(bench, bench.dm_id, due=T0.replace(hour=15, minute=55))
    evening = T0.replace(hour=19)  # 20:00 in Berlin, after an outage
    fired = await fire(bench, evening)
    assert (fired.outcome, fired.run_id) == (FiringOutcome.SKIPPED_OFF_HOURS, None)
    assert await runs_of(bench.session, automation.id) == []
    assert (await reload(bench.session, automation.id)).next_due_at == TOMORROW_NINE
    a_little_late = TOMORROW_NINE + timedelta(minutes=3)  # a few minutes late still runs
    assert (await fire(bench, a_little_late)).outcome == FiringOutcome.STARTED


async def test_a_heartbeat_asking_for_a_release_opens_its_thread_for_the_card(
    work: Work,
) -> None:
    bench, channel = work.bench, await _channel(work)
    page_id = await work.page()
    await confirm(work, "propose_page_change")
    args = {"page_id": page_id, "content_md": NEW, "reason": "Veraltet"}
    bench.stub.state.replies.append(call("propose_page_change", **args))
    await beating(bench, channel)
    await fire(bench)
    assert await bench.run_next() is None  # waits for the release
    said = await messages_in(bench.session, channel)
    (root,) = [m for m in said if m.parent_id is None]
    assert root.kind == MessageKind.SYSTEM
    (card,) = [m for m in said if m.parent_id == root.id]
    assert card.kind == MessageKind.APPROVAL


async def _live_since(bench: Bench, since: Any) -> list[Any]:
    rows = await bench.session.scalars(select(EventOutbox).where(EventOutbox.id > since))
    return [e for e in (of_event(Event.of(row)) for row in rows) if e is not None]


async def test_a_silent_heartbeat_sends_nothing_live_into_its_place(work: Work) -> None:
    """No "is working" card for the place's readers at every interval (review M7,
    finding 5): its progress goes to its owner alone, whose run view follows it."""
    bench, channel = work.bench, await _channel(work)
    await beating(bench, channel)
    since = await _last_event_id(bench)
    fired = await fire(bench)
    bench.stub.state.replies.append({"content": "HEARTBEAT_OK"})
    assert await bench.run_next() == StopReason.COMPLETED
    live = await _live_since(bench, since)
    told = sorted({e.name for e in live if e.conversation_id == channel})
    assert told == [], f"live events for the heartbeat's place: {told}"
    progress = [(e.user_id, e.run_id) for e in live if e.name == "run.progress"]
    assert progress == [(bench.people.users["alice"].id, fired.run_id)]


async def test_a_heartbeat_that_delivers_goes_live_in_its_place_from_then_on(work: Work) -> None:
    """Once its term's thread is open (here: a card waits for a release), its progress
    goes to the place like any run's."""
    bench, channel = work.bench, await _channel(work)
    page_id = await work.page()
    await confirm(work, "propose_page_change")
    args = {"page_id": page_id, "content_md": NEW, "reason": "Veraltet"}
    bench.stub.state.replies.extend([call("propose_page_change", **args), {"content": "Fertig"}])
    await beating(bench, channel)
    await fire(bench)
    assert await bench.run_next() is None  # waits for the release, its card in the thread
    r = await bench.people.alice.get("/api/approvals", params={"state": "pending"})
    (approval,) = r.json()["items"]
    since = await _last_event_id(bench)
    assert (await decide(work, approval, "approve")).status_code == 200
    assert await bench.run_next() == StopReason.COMPLETED
    live = await _live_since(bench, since)
    progress = [(e.conversation_id, e.user_id) for e in live if e.name == "run.progress"]
    assert progress and set(progress) == {(channel, None)}
