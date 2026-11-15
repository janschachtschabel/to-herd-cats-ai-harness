"""A released call whose step timed out (module review M6 2, finding 7): the step is
rolled back whole, `outcome = ran` with it, and the call's recorded result is the
timeout, so the run never comes back to the release. The approval records `failed`
in the transaction that records the timeout; the API and the card say so."""

from typing import Any

import pytest

from app.modules.agents.run_models import StopReason
from app.modules.agents.step_records import TOOL_TIMED_OUT
from app.modules.proposals.service import ProposalService
from tests.factories_writing import Work, events
from tests.test_approvals import asked, decide, proposals


class _StatementTimeout(Exception):
    sqlstate = "57014"  # as asyncpg names a statement that ran past its bound


async def test_a_released_call_that_times_out_is_recorded_failed(
    work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    page_id = await work.page()
    _, approval = await asked(work, page_id)
    assert (await decide(work, approval, "approve")).status_code == 200

    async def too_slow(*args: Any, **kwargs: Any) -> Any:
        raise _StatementTimeout

    monkeypatch.setattr(ProposalService, "propose_change", too_slow)
    assert await work.bench.run_next() == StopReason.COMPLETED
    assert TOOL_TIMED_OUT in work.bench.stub.state.texts()
    assert await proposals(work) == []
    shown = (await work.bench.people.alice.get(f"/api/approvals/{approval['id']}")).json()
    assert shown["state"] == "approved" and shown["outcome"] == "failed"
    (settled,) = await events(work.bench.session, "approval.settled")  # the card is told
    assert settled.payload["approval_id"] == approval["id"]
