"""What the budget screens were missing (plan M7 task 7, gaps found by task 9a): a slim
list of agents for whoever administers AI (`ai.manage`, without `agent.manage`
needed), which limit of a budget is reached today (tokens, cost), and whose limit a
run's `budget` stop notice names."""

import pytest

from app.modules.agents.run_models import StopReason
from app.modules.ai.models import BudgetScope
from tests.factories_agents import Bench, make_agent
from tests.factories_external_agents import make_external
from tests.factories_writing import Work
from tests.test_ai_budget_check import budget
from tests.test_ai_budgets import BUDGETS, listed, put, use

AGENTS = f"{BUDGETS}/agents"


async def test_who_administers_ai_finds_every_agent_by_name(bench: Bench) -> None:
    second = await make_agent(bench.session, bench.people, bench.connection.id, name="Bruno")
    r = await bench.people.admin.get(f"{AGENTS}?limit=1")
    assert r.status_code == 200, r.text
    assert r.json()["items"] == [{"id": str(bench.agent.id), "name": "Ava"}]
    rest = await bench.people.admin.get(f"{AGENTS}?limit=1&cursor={r.json()['next_cursor']}")
    assert rest.json() == {"items": [{"id": str(second.id), "name": "Bruno"}], "next_cursor": None}
    for who in ("alice", "gast"):
        refused = await getattr(bench.people, who).get(AGENTS)
        assert refused.status_code == 404 and refused.json()["error"]["code"] == "ai.not_found"


async def test_external_agents_are_no_budget_subjects(work: Work) -> None:
    """Module review M8 1, finding 13: an external agent uses no model, so no budget."""
    await make_external(work, name="Aaron")
    r = await work.admin.get(AGENTS)
    assert [a["name"] for a in r.json()["items"]] == ["Ava"]


@pytest.mark.parametrize(
    ("limits", "reached"),
    [
        ({"tokens_per_day": 100}, (True, False)),
        ({"cost_per_day": "0.10"}, (False, True)),
        ({"tokens_per_day": 100, "cost_per_day": "0.10"}, (True, True)),
        ({"tokens_per_day": 1000, "cost_per_day": "5"}, (False, False)),
    ],
)
async def test_the_list_says_which_limit_is_reached(
    bench: Bench, limits: dict[str, object], reached: tuple[bool, bool]
) -> None:
    bench.connection.prices = {"m1": {"input": "1000", "output": "1000"}}  # EUR per M tokens
    await bench.session.flush()
    await put(bench, "organisation", **limits)
    await use(bench)  # 150 tokens, 0.15 EUR
    (shown,) = await listed(bench)
    today = shown["today"]
    assert (today["tokens_reached"], today["cost_reached"]) == reached
    assert today["exhausted"] is any(reached)


@pytest.mark.parametrize("scope", [BudgetScope.USER, BudgetScope.AGENT, BudgetScope.ORGANISATION])
async def test_a_budget_stop_names_whose_limit_was_reached(
    bench: Bench, scope: BudgetScope
) -> None:
    await budget(bench, scope, tokens_per_day=100)
    await use(bench, agent=True)
    await bench.say("Hallo")
    assert await bench.run_next() == StopReason.BUDGET
    (notice,) = [m for m in await bench.messages() if m["kind"] == "system"]
    assert notice["system"]["new"]["value"] == "budget"
    assert notice["system"]["budget_scope"] == scope.value


async def test_other_stops_name_no_budget(bench: Bench) -> None:
    await bench.say("Hallo")
    bench.stub.state.failures.extend([401])  # the provider refuses: `error`
    await bench.run_next()
    notices = [m for m in await bench.messages() if m["kind"] == "system"]
    assert notices and all(n["system"]["budget_scope"] is None for n in notices)
    assert all(n["system"]["stop_detail"] is None for n in notices)
