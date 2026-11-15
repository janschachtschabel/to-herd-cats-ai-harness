"""Firing a due automation (plan M7 task 2), in the test's transaction: the run, the
log row and the next term together; `once` fires once; the busy and the paused agent
are skipped and logged; after an outage one catch-up, not one per missed term;
daylight saving time in `Europe/Berlin`; the log takes a term once."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.agents.models import AgentStatus
from app.modules.agents.run_models import RunState
from app.modules.automations.firing import fire_next
from app.modules.automations.models import Automation, AutomationState, FiringOutcome
from app.modules.automations.repository import AutomationRepository
from tests.factories_agents import Bench
from tests.factories_automations import automation_row, finish_runs, firings, reload, runs_of

T0 = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)  # a Monday, 10:00 in Berlin


async def _automation(bench: Bench, *, due: datetime = T0, **fields: object) -> Automation:
    alice = bench.people.users["alice"]
    row = automation_row(
        alice.org_id,
        alice.id,
        bench.agent.id,
        bench.dm["id"],
        due=due,
        **fields,  # type: ignore[arg-type]
    )
    bench.session.add(row)
    await bench.session.flush()
    return row


async def test_a_due_automation_starts_a_run_logs_it_and_takes_the_next_term(
    bench: Bench,
) -> None:
    automation = await _automation(bench)
    fired = await fire_next(bench.session, T0 + timedelta(seconds=3))
    assert fired is not None and fired.outcome == FiringOutcome.STARTED
    [run] = await runs_of(bench.session, automation.id)
    alice = bench.people.users["alice"]
    assert (run.state, run.user_id, run.agent_id) == (RunState.QUEUED, alice.id, bench.agent.id)
    assert str(run.conversation_id) == bench.dm["id"]
    assert (run.lane_id, run.automation_id) == (automation.id, automation.id)
    assert (run.chain_depth, run.trigger_message_id, run.work_item_id) == (0, None, None)
    [logged] = await firings(bench.session, automation.id)
    assert (logged.due_at, logged.fired_at) == (T0, T0 + timedelta(seconds=3))
    assert (logged.outcome, logged.run_id, logged.org_id) == ("started", run.id, alice.org_id)
    after = await reload(bench.session, automation.id)
    assert after.next_due_at == T0 + timedelta(hours=1)
    assert after.state == AutomationState.ACTIVE


async def test_nothing_fires_before_its_term(bench: Bench) -> None:
    automation = await _automation(bench)
    assert await fire_next(bench.session, T0 - timedelta(seconds=1)) is None
    assert await firings(bench.session, automation.id) == []


async def test_once_fires_once_and_never_again(bench: Bench) -> None:
    automation = await _automation(bench, cron=None)
    fired = await fire_next(bench.session, T0)
    assert fired is not None and fired.outcome == FiringOutcome.STARTED
    after = await reload(bench.session, automation.id)
    assert (after.state, after.next_due_at) == (AutomationState.DONE, None)
    await finish_runs(bench.session)
    assert await fire_next(bench.session, T0 + timedelta(days=400)) is None
    assert len(await firings(bench.session, automation.id)) == 1
    assert len(await runs_of(bench.session, automation.id)) == 1


async def test_a_term_while_the_previous_run_is_open_is_skipped_busy(bench: Bench) -> None:
    automation = await _automation(bench)
    await fire_next(bench.session, T0)
    second = T0 + timedelta(hours=1)
    fired = await fire_next(bench.session, second)
    assert fired is not None and fired.outcome == FiringOutcome.SKIPPED_BUSY
    assert len(await runs_of(bench.session, automation.id)) == 1
    logged = await firings(bench.session, automation.id)
    assert [(f.due_at, f.outcome, f.run_id) for f in logged[1:]] == [(second, "skipped_busy", None)]
    assert (await reload(bench.session, automation.id)).next_due_at == T0 + timedelta(hours=2)
    await finish_runs(bench.session)  # the previous run ends: the next term starts one
    fired = await fire_next(bench.session, T0 + timedelta(hours=2))
    assert fired is not None and fired.outcome == FiringOutcome.STARTED
    assert len(await runs_of(bench.session, automation.id)) == 2


async def test_a_run_waiting_for_an_answer_keeps_the_automation_busy(bench: Bench) -> None:
    automation = await _automation(bench)
    await fire_next(bench.session, T0)
    [run] = await runs_of(bench.session, automation.id)
    run.state, run.wait_until = RunState.WAITING, T0 + timedelta(days=1)
    await bench.session.flush()
    fired = await fire_next(bench.session, T0 + timedelta(hours=1))
    assert fired is not None and fired.outcome == FiringOutcome.SKIPPED_BUSY


async def test_after_an_outage_it_fires_once_and_takes_the_term_after_now(bench: Bench) -> None:
    automation = await _automation(bench)
    late = T0 + timedelta(hours=5, minutes=30)  # five terms missed
    fired = await fire_next(bench.session, late)
    assert fired is not None and fired.due_at == T0
    assert await fire_next(bench.session, late) is None
    assert [f.due_at for f in await firings(bench.session, automation.id)] == [T0]
    assert (await reload(bench.session, automation.id)).next_due_at == T0 + timedelta(hours=6)


async def test_a_paused_agent_starts_no_run_and_the_term_is_logged(bench: Bench) -> None:
    automation = await _automation(bench)
    bench.agent.status = AgentStatus.PAUSED
    await bench.session.flush()
    fired = await fire_next(bench.session, T0)
    assert fired is not None and fired.outcome == FiringOutcome.SKIPPED_PAUSED_AGENT
    assert await runs_of(bench.session, automation.id) == []
    [logged] = await firings(bench.session, automation.id)
    assert (logged.outcome, logged.run_id) == ("skipped_paused_agent", None)
    assert (await reload(bench.session, automation.id)).next_due_at == T0 + timedelta(hours=1)


async def test_a_paused_automation_fires_nothing(bench: Bench) -> None:
    automation = await _automation(bench, paused=True)
    assert await fire_next(bench.session, T0 + timedelta(days=1)) is None
    assert await firings(bench.session, automation.id) == []
    assert (await reload(bench.session, automation.id)).next_due_at == T0


async def test_the_most_overdue_fires_first(bench: Bench) -> None:
    later = await _automation(bench, due=T0)
    earlier = await _automation(bench, due=T0 - timedelta(hours=3))
    first = await fire_next(bench.session, T0)
    second = await fire_next(bench.session, T0)
    assert first is not None and second is not None
    assert (first.automation_id, second.automation_id) == (earlier.id, later.id)


async def test_daylight_saving_time_ends_a_doubled_time_fires_once(bench: Bench) -> None:
    # 25 October 2026 in Berlin: 02:30 happens at 00:30 and at 01:30 UTC
    first = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    automation = await _automation(bench, due=first, cron="30 2 * * *")
    assert await fire_next(bench.session, first) is not None
    await finish_runs(bench.session)
    assert await fire_next(bench.session, datetime(2026, 10, 25, 1, 31, tzinfo=UTC)) is None
    assert (await reload(bench.session, automation.id)).next_due_at == datetime(
        2026, 10, 26, 1, 30, tzinfo=UTC
    )


async def test_daylight_saving_time_starts_a_missing_time_falls_to_the_next(
    bench: Bench,
) -> None:
    # 29 March 2026 in Berlin: 02:30 does not exist; the term is 03:00 CEST (01:00 UTC)
    automation = await _automation(
        bench, due=datetime(2026, 3, 28, 1, 30, tzinfo=UTC), cron="30 2 * * *"
    )
    assert await fire_next(bench.session, datetime(2026, 3, 28, 1, 30, tzinfo=UTC)) is not None
    spring = datetime(2026, 3, 29, 1, 0, tzinfo=UTC)
    assert (await reload(bench.session, automation.id)).next_due_at == spring
    await finish_runs(bench.session)
    assert await fire_next(bench.session, spring - timedelta(seconds=1)) is None
    fired = await fire_next(bench.session, spring)
    assert fired is not None and fired.due_at == spring


async def test_the_log_takes_each_term_once(bench: Bench) -> None:
    automation = await _automation(bench)
    log = AutomationRepository(bench.session, automation.org_id)
    await log.log(automation, T0, T0, FiringOutcome.SKIPPED_BUSY)
    nested = await bench.session.begin_nested()
    with pytest.raises(IntegrityError, match="uq_automation_firing_term"):
        await log.log(automation, T0, T0 + timedelta(seconds=1), FiringOutcome.SKIPPED_BUSY)
    await nested.rollback()
