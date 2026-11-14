"""The run view's cancel waits for a run's row only briefly (plan M7 decision 15), like
taking a ticket from an agent (review M6 2, finding 4): a step that holds the row
(a step may take 20 s and more) makes it answer 409 `conflict.retry` with
`Retry-After` within `REASSIGN_LOCK_TIMEOUT_SECONDS`; sent again once the step is
done, it goes through. Real commits on separate connections."""

import asyncio
import time

from sqlalchemy import select

from app.modules.agents.executor_repository import RunSteps
from app.modules.agents.models import REASSIGN_LOCK_TIMEOUT_SECONDS
from app.modules.agents.run_control_models import RunCancelRequest
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub
from tests.test_run_row_locks import _ticket_run


async def test_cancelling_waits_for_a_running_step_only_briefly(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    owner, _, claimed = await _ticket_run(real_db, make_real_client, openai_stub)
    url = f"/api/runs/{claimed.id}/cancel"
    async with real_db.database.session_factory() as step, step.begin():
        assert await RunSteps(step, claimed).owned() is not None  # as every step
        started = time.monotonic()
        request = asyncio.create_task(owner.post(url))
        done, _ = await asyncio.wait({request}, timeout=REASSIGN_LOCK_TIMEOUT_SECONDS + 2.0)
        took = time.monotonic() - started
    assert done, "POST /api/runs/{id}/cancel waited for the run's step to end"
    response = request.result()
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "conflict.retry"
    assert response.headers["Retry-After"] == "1"
    assert took >= REASSIGN_LOCK_TIMEOUT_SECONDS * 0.9
    async with real_db.database.session_factory() as session:
        assert list(await session.scalars(select(RunCancelRequest.run_id))) == []
    again = await owner.post(url)
    assert again.status_code == 200, again.text
    async with real_db.database.session_factory() as session:
        assert list(await session.scalars(select(RunCancelRequest.run_id))) == [claimed.id]
