"""Terms an automation skips (plan M7 decisions 6, 10 and 13), logged without a run:
a daily budget reached (`skipped_budget`), the place closed to AI or archived
(`skipped_policy`). Three runs in a row that do not end `completed` pause it
(`failing`), and its owner learns of it; a completed run starts the count anew. A
cancelled run and one a daily budget stopped neither count nor start it anew."""

import uuid
from datetime import timedelta

from app.core.models_base import utcnow
from app.modules.agents.models import StopReason
from app.modules.ai.models import AiPolicy, BudgetScope
from app.modules.automations.firing import fire_next
from app.modules.automations.models import AutomationState, FiringOutcome, PausedReason
from app.modules.automations.runs import ended
from app.modules.messaging.models import Conversation
from tests.factories_agents import Bench
from tests.factories_automations import T0, fire, firings, notified, placed, reload, runs_of
from tests.factories_writing import Work, messages_in
from tests.test_ai_budget_check import budget
from tests.test_ai_budgets import use


async def test_a_reached_budget_skips_the_term(bench: Bench) -> None:
    now = utcnow()  # budgets count the UTC day of the term
    automation = await placed(bench, bench.dm_id, due=now - timedelta(minutes=1))
    await budget(bench, BudgetScope.AGENT, tokens_per_day=100)
    await use(bench, agent=True)  # 150 tokens of the agent's today
    fired = await fire(bench, now)
    assert (fired.outcome, fired.run_id) == (FiringOutcome.SKIPPED_BUDGET, None)
    [logged] = await firings(bench.session, automation.id)
    assert (logged.outcome, logged.run_id, logged.instruction) == ("skipped_budget", None, None)
    assert await runs_of(bench.session, automation.id) == []
    after = await reload(bench.session, automation.id)
    assert after.state == AutomationState.ACTIVE and after.next_due_at is not None
    assert after.next_due_at > now  # the next term comes as usual


async def _channel(work: Work) -> uuid.UUID:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "bericht"})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


async def test_a_space_closed_to_ai_skips_the_term(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    automation = await placed(bench, channel)
    work.space.ai_policy = AiPolicy.NONE
    await bench.session.flush()
    fired = await fire(bench)
    assert (fired.outcome, fired.run_id) == (FiringOutcome.SKIPPED_POLICY, None)
    assert await runs_of(bench.session, automation.id) == []
    assert await messages_in(bench.session, channel) == []  # no thread opened
    work.space.ai_policy = AiPolicy.ANY  # open again: the next term runs
    await bench.session.flush()
    assert (await fire(bench, T0 + timedelta(hours=1))).outcome == FiringOutcome.STARTED


async def test_an_archived_channel_skips_the_term(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    automation = await placed(bench, channel)
    place = await bench.session.get(Conversation, channel)
    assert place is not None
    place.archived_at = utcnow()
    await bench.session.flush()
    fired = await fire(bench)
    assert fired.outcome == FiringOutcome.SKIPPED_POLICY
    assert (await reload(bench.session, automation.id)).state == AutomationState.ACTIVE


async def _term(bench: Bench, hour: int, *, fail: bool) -> StopReason | None:
    await fire(bench, T0 + timedelta(hours=hour))
    if fail:
        bench.stub.state.failures.append(401)
    else:
        bench.stub.state.replies.append({"content": "ok"})
    return await bench.run_next()


async def test_three_failures_in_a_row_pause_it_and_tell_the_owner(bench: Bench) -> None:
    automation = await placed(bench, bench.dm_id)
    for hour in range(3):
        assert await _term(bench, hour, fail=True) == StopReason.PROVIDER_REFUSED
    after = await reload(bench.session, automation.id)
    assert (after.state, after.paused_reason) == (AutomationState.PAUSED, PausedReason.FAILING)
    assert after.failures == 0  # a resume starts the count anew
    alice = bench.people.users["alice"]
    assert await notified(bench.session, automation.id) == [(alice.id, "automation")]
    r = await bench.people.alice.get("/api/activity")
    (entry,) = [a for a in r.json()["items"] if a["reason"] == "automation"]
    assert entry["automation"] == {"id": str(automation.id), "paused_reason": "failing"}
    assert len(await runs_of(bench.session, automation.id)) == 3
    assert await fire_next(bench.session, T0 + timedelta(hours=5)) is None


async def test_a_completed_run_starts_the_count_anew(bench: Bench) -> None:
    automation = await placed(bench, bench.dm_id)
    assert await _term(bench, 0, fail=True) == StopReason.PROVIDER_REFUSED
    assert await _term(bench, 1, fail=True) == StopReason.PROVIDER_REFUSED
    assert await _term(bench, 2, fail=False) == StopReason.COMPLETED
    assert await _term(bench, 3, fail=True) == StopReason.PROVIDER_REFUSED
    after = await reload(bench.session, automation.id)
    assert (after.state, after.failures) == (AutomationState.ACTIVE, 1)
    assert await notified(bench.session, automation.id) == []


async def test_a_cancelled_or_budget_stopped_run_neither_counts_nor_resets(bench: Bench) -> None:
    automation = await placed(bench, bench.dm_id)
    org = automation.org_id
    await ended(bench.session, org, automation.id, StopReason.PROVIDER_REFUSED)
    await ended(bench.session, org, automation.id, StopReason.PROVIDER_REFUSED)
    for reason in (StopReason.CANCELLED, StopReason.BUDGET):
        await ended(bench.session, org, automation.id, reason)
        after = await reload(bench.session, automation.id)
        assert (after.state, after.failures) == (AutomationState.ACTIVE, 2)
    await ended(bench.session, org, automation.id, StopReason.ERROR)  # the third in a row
    after = await reload(bench.session, automation.id)
    assert (after.state, after.paused_reason) == (AutomationState.PAUSED, PausedReason.FAILING)
