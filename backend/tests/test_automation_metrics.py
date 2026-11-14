"""Metrics of automations, budgets and the page review (plan M7 task 11): ids and
outcomes as labels only. The due loop's gauges are read from the database (due
automations and the lag of the oldest due term, paused ones by reason, spaces the
review pass has still to go through today); terms fired by the event handler are
counted like those of the due loop, once their delivery committed; a budget stop is
counted by the budget's scope; the review pass counts the pages it reminded."""

from datetime import timedelta

from sqlalchemy import select

from app.core.metrics import REGISTRY
from app.modules.agents.models import StopReason
from app.modules.ai.models import BudgetScope
from app.modules.automations.models import Automation, AutomationState, PausedReason
from app.worker.dispatcher import Dispatcher
from app.worker.due import DueLoop
from app.worker.registry import REGISTRY as HANDLERS
from tests.factories_agents import Bench
from tests.factories_automations import automation_row
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.support.openai_stub import OpenAIStub
from tests.test_ai_budget_check import budget
from tests.test_ai_budgets import use
from tests.test_automation_due_loop import T0, _place
from tests.test_automation_event_workers import _rule
from tests.test_wiki_review_workers import T0 as REVIEW_T0
from tests.test_wiki_review_workers import _spaces


def _sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def test_the_gauges_show_what_is_due_and_how_late_the_oldest_term_is(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    place = await _place(real_db, make_real_client, openai_stub)
    args = (place["org"], place["owner"], place["agent"], place["dm"])
    async with real_db.database.session_factory() as session:
        session.add_all(
            [
                automation_row(*args, due=T0 - timedelta(seconds=120)),
                automation_row(*args, due=T0 - timedelta(seconds=30)),
                automation_row(*args, due=T0 + timedelta(seconds=60)),  # not yet
                automation_row(*args, due=T0 - timedelta(hours=1), paused=True),
            ]
        )
        await session.commit()
    loop = DueLoop(real_db.database, clock=SettableClock(T0))
    await loop.update_metrics()
    assert _sample("herd_automations_due") == 2
    assert _sample("herd_automations_oldest_due_seconds") == 120
    assert _sample("herd_automations_paused", reason=PausedReason.MANUAL) == 1
    assert _sample("herd_automations_paused", reason=PausedReason.FAILING) == 0
    assert await loop.pass_once() == 2
    await loop.update_metrics()
    assert _sample("herd_automations_due") == 0
    assert _sample("herd_automations_oldest_due_seconds") == 0
    async with real_db.database.session_factory() as session:
        rows = (await session.scalars(select(Automation))).all()
        for row in rows:
            if row.state == AutomationState.PAUSED:
                row.paused_reason = PausedReason.FAILING
        await session.commit()
    await loop.update_metrics()
    assert _sample("herd_automations_paused", reason=PausedReason.MANUAL) == 0
    assert _sample("herd_automations_paused", reason=PausedReason.FAILING) == 1


async def test_terms_the_event_handler_fires_are_counted(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    DueLoop(real_db.database)  # a worker process: its metrics are registered
    before = _sample("herd_automation_firings_total", outcome="started")
    await _rule(real_db, make_real_client, openai_stub)  # six tickets: one term, five wait
    await Dispatcher(real_db.database, HANDLERS).drain()
    assert _sample("herd_automation_firings_total", outcome="started") == before + 1


async def test_the_review_pass_counts_its_reminders_and_the_spaces_left(
    real_db: RealDb,
) -> None:
    await _spaces(real_db, 2, 3)
    loop = DueLoop(real_db.database, clock=SettableClock(REVIEW_T0))
    before = _sample("herd_wiki_review_reminders_total")
    await loop.update_metrics()
    assert _sample("herd_wiki_review_spaces_unchecked") == 2
    await loop.round()
    assert _sample("herd_wiki_review_reminders_total") == before + 6
    await loop.update_metrics()
    assert _sample("herd_wiki_review_spaces_unchecked") == 0


async def test_a_budget_stop_is_counted_by_its_scope(bench: Bench) -> None:
    before = _sample("herd_budget_stops_total", scope="user")
    agent_before = _sample("herd_budget_stops_total", scope="agent")
    await budget(bench, BudgetScope.USER, tokens_per_day=100)
    await use(bench)  # 150 tokens of Alice's today
    await bench.say("Hallo")
    assert await bench.run_next() == StopReason.BUDGET
    assert _sample("herd_budget_stops_total", scope="user") == before + 1
    assert _sample("herd_budget_stops_total", scope="agent") == agent_before
