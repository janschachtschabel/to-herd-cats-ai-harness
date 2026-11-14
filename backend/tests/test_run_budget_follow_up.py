"""A DM's run that a daily budget stopped queues no run for a message that came while
it waited (plan M7 decision 10; Task 1's report): that run would stop again at its
first call and only add another notice."""

from sqlalchemy import select

from app.modules.agents.models import Run, RunState, StopReason
from app.modules.ai.models import BudgetScope
from tests.factories_tools import call
from tests.factories_writing import Work
from tests.test_ai_budget_check import budget
from tests.test_approvals import NEW, confirm, decide


async def test_a_run_stopped_by_its_budget_queues_no_follow_up(work: Work) -> None:
    bench = work.bench
    page_id = await work.page()
    await confirm(work, "propose_page_change")
    args = {"page_id": page_id, "content_md": NEW, "reason": "Klarer"}
    bench.stub.state.replies.extend([call("propose_page_change", **args), {"content": "ok"}])
    await bench.say("Bitte verbessern")
    assert await bench.run_next() is None  # waits for Alice's release
    await bench.say("Und noch etwas")  # no run of its own while the first one waits
    await budget(bench, BudgetScope.USER, tokens_per_day=1)  # the first call used more
    r = await bench.people.alice.get("/api/approvals", params={"state": "pending"})
    (approval,) = r.json()["items"]
    assert (await decide(work, approval, "approve")).status_code == 200
    assert await bench.run_next() == StopReason.BUDGET
    left = await bench.session.scalars(select(Run).where(Run.state != RunState.DONE))
    assert list(left) == []
