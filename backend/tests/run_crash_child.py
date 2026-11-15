"""A run worker to be killed (tests/test_run_crash.py). It claims the next run and works
it until the point named in argv[1], says that point on stdout and waits there:

- `after-model`: step 1's model call is recorded (committed), its tool has not run;
- `in-tool`: `probe_write` has written its effect, its transaction is still open;
- `after-tool`: the tool's effect and its journal entry are committed.
"""

import asyncio
import os
import sys
from typing import Any

import app.models_registry  # noqa: F401 -- every model, as in the worker
from app.core.config import get_settings
from app.core.db import Database
from app.modules.agents.executor import Executor
from app.modules.agents.executor_repository import claim
from app.modules.agents.step_host import RunHost, units_of
from tests.support import probe_tools


def stop_after(method: str, point: str) -> None:
    original = getattr(RunHost, method)

    async def stopping(self: RunHost, step: int, *args: Any) -> Any:
        result = await original(self, step, *args)
        sys.stdout.write(f"{point}\n")
        sys.stdout.flush()
        await asyncio.sleep(3600)
        return result

    setattr(RunHost, method, stopping)


async def main(point: str) -> None:
    probe_tools.install()
    if point == "in-tool":
        os.environ["HERD_PROBE_HANG"] = "in-tool"
    else:
        stop_after("after_model_call" if point == "after-model" else "call_tool", point)
    database = Database(get_settings().test_database_url)
    async with database.session_factory() as session, session.begin():
        claimed = await claim(session, 300)
    assert claimed is not None, "no run to claim"
    await Executor(units_of(database.session_factory)).execute(claimed)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
