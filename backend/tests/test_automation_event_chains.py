"""Chains of event rules (plan M7 decision 9, review focus 3): an event a run caused
names the run (`event_outbox.run_id`), and a run it starts is one step further down
that run's chain (`chain_depth` + 1, handovers and events counted together); past
depth 3 no run starts (`skipped_depth`). Two rules in a circle stop the same way. A
rule never reacts to an event its own run caused on an object that run was about."""

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.core.outbox import caused_by
from app.modules.agents.models import Run, RunState, StopReason
from app.modules.automations.event_models import AutomationEvent
from app.modules.automations.models import Automation, FiringOutcome
from app.modules.wiki.events import PAGE_PUBLISHED, page_event
from app.modules.wiki.models import Page
from tests.factories_automations import T0, finish_runs, firings, ruled, runs_of
from tests.factories_tools import call
from tests.factories_writing import Work
from tests.test_access import actor_of
from tests.test_automation_events import QUIET, _channel, take_in
from tests.test_automation_live_terms import told

STEP = timedelta(seconds=QUIET + 1)


async def _creates(work: Work, kind: str = "task") -> None:
    """The next run creates a ticket of `kind` in the space, then answers."""
    args: dict[str, Any] = {"space_id": str(work.space.id), "title": "Folge", "kind": kind}
    work.bench.stub.state.replies.extend([call("create_ticket", **args), {"content": "Ok."}])


async def _depths(work: Work, *rules: Automation) -> list[int]:
    found = []
    for rule in rules:
        found += [run.chain_depth for run in await runs_of(work.bench.session, rule.id)]
    return sorted(found)


async def test_a_chain_stops_at_depth_three(work: Work) -> None:
    bench = work.bench
    bench.agent.level = 2
    await bench.session.flush()
    rule = await ruled(bench, await _channel(work))
    await work.ticket("Anfang")  # a person's: depth 0
    at = T0
    await take_in(bench, "ticket.created", at)
    for _ in range(4):
        await _creates(work)
        assert await bench.run_next() == StopReason.COMPLETED
        at += STEP
        await take_in(bench, "ticket.created", at)  # the ticket the run created
    assert await _depths(work, rule) == [0, 1, 2, 3]
    logged = await firings(bench.session, rule.id)
    assert [f.outcome for f in logged] == ["started"] * 4 + [FiringOutcome.SKIPPED_DEPTH]
    assert len(await told(work, rule.id)) == len(logged)  # one live event per term
    assert logged[-1].run_id is None


async def test_two_rules_in_a_circle_stop(work: Work) -> None:
    """A answers a task with a bug, B a bug with a task."""
    bench = work.bench
    bench.agent.level = 2
    await bench.session.flush()
    on_task = await ruled(bench, await _channel(work, "a"), ticket_kind="task")
    on_bug = await ruled(bench, await _channel(work, "b"), ticket_kind="bug")
    await work.ticket("Anfang", kind="task")
    at = T0
    await take_in(bench, "ticket.created", at)
    for kind in ("bug", "task", "bug", "task"):
        await _creates(work, kind)
        assert await bench.run_next() == StopReason.COMPLETED
        at += STEP
        await take_in(bench, "ticket.created", at)
    assert await _depths(work, on_task) == [0, 2]
    assert await _depths(work, on_bug) == [1, 3]
    last = (await firings(bench.session, on_task.id))[-1]
    assert last.outcome == FiringOutcome.SKIPPED_DEPTH
    open_runs = await bench.session.scalars(select(Run.id).where(Run.state != RunState.DONE))
    assert list(open_runs) == []  # nothing left to run


async def test_its_own_effect_on_the_same_object_starts_nothing(work: Work) -> None:
    bench = work.bench
    rule = await ruled(bench, await _channel(work), "page.published")
    page_id = await work.page()
    await take_in(bench, PAGE_PUBLISHED, T0)
    [run] = await runs_of(bench.session, rule.id)
    await finish_runs(bench.session)
    page = await bench.session.get(Page, uuid.UUID(page_id))
    other = await bench.session.get(Page, uuid.UUID(await work.page("Anderes")))
    assert page is not None and other is not None
    agent = await actor_of(bench.session, bench.people.users["admin"])
    with caused_by(run.id):  # as if the run's step had published the page again
        await page_event(bench.session, agent, PAGE_PUBLISHED, page)
    await take_in(bench, PAGE_PUBLISHED, T0 + STEP)
    assert len(await firings(bench.session, rule.id)) == 1
    with caused_by(run.id):  # another page: a chain, one step down
        await page_event(bench.session, agent, PAGE_PUBLISHED, other)
    await take_in(bench, PAGE_PUBLISHED, T0 + 2 * STEP)
    runs = await bench.session.scalars(select(Run).where(Run.automation_id == rule.id))
    assert sorted(r.chain_depth for r in runs) == [0, 1]
    taken = await bench.session.scalars(select(AutomationEvent.subject_id))
    assert sorted(map(str, taken)) == sorted([page_id, str(other.id)])
