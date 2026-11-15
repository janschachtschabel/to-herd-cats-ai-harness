"""A dispatcher to be killed (tests/test_dispatcher_crash.py): lane `first` commits its
batch; handler `second` writes its effect, says `in-second` on stdout and then waits
inside its lane's open transaction until the parent kills the process."""

import asyncio
import sys
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import Database
from app.core.outbox import Event
from app.worker.dispatcher import Dispatcher
from tests.outbox_helpers import Calls, registry_of, write_effect


async def main() -> None:
    calls: Calls = Counter()
    registry = registry_of(calls, ["first"])

    @registry.handler("test", "second")
    async def _second(session: AsyncSession, event: Event) -> None:
        await write_effect(session, event, "second")
        await session.flush()
        sys.stdout.write("in-second\n")
        sys.stdout.flush()
        await asyncio.sleep(3600)

    database = Database(get_settings().test_database_url)
    dispatcher = Dispatcher(database, registry)
    await dispatcher.route()
    first, second = dispatcher.handlers
    await dispatcher.dispatch_lane(first)
    await dispatcher.dispatch_lane(second)


if __name__ == "__main__":
    asyncio.run(main())
