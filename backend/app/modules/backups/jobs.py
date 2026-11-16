"""The worker takes up an owner's "Jetzt sichern" (plan M9 task 13): the request is a
`backup_run` row with trigger `admin` in state `running` (`service.request`), and every
POLL_SECONDS a worker looks for the oldest one younger than REQUEST_GRACE and runs it
as a whole backup run (`ops/cli_run.run_backup` with its id: archive, read back,
retention, offsite), as the command line would. The backup lock keeps it to one
backup at a time across workers and the scheduled job: while another backup holds it
the request waits for the next look. A worker that dies midway leaves the row
`running`; the next look within the grace takes it up again, later the upkeep marks it
`interrupted` like any backup whose process died. A backup refused before it began
(the database not at this code's revision, say) ends the request `failed` with the
refusal's code.

In maintenance (`paused`) no request is taken up. Outside the worker's readiness, like
the run and due loops; at most two database connections while a backup runs (its
lock holder and one session), none between looks but the query's.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from contextlib import suppress

from app.core.clock import SYSTEM_CLOCK, Clock
from app.core.config import Settings, get_settings
from app.core.db import Database
from app.modules.backups.live import tell_managers
from app.modules.backups.models import BackupState, BackupTrigger
from app.modules.backups.repository import REQUEST_GRACE, BackupRunRepository
from app.modules.maintenance.cache import in_maintenance
from app.ops.cli_run import run_backup

logger = logging.getLogger(__name__)

POLL_SECONDS = 3.0
MAX_ERROR_WAIT_SECONDS = 30.0
# Outcomes that leave the request as it is: another backup holds the lock, or the
# request was ended meanwhile.
WAITING = frozenset({"backup.already_running", "backup.request_gone"})


class BackupJobLoop:
    def __init__(
        self,
        database: Database,
        *,
        settings: Callable[[], Settings] = get_settings,
        clock: Clock = SYSTEM_CLOCK,
        paused: Callable[[], bool] = in_maintenance,
    ) -> None:
        self.database = database
        self.settings = settings
        self.clock = clock
        self.paused = paused

    async def serve(self, stop: asyncio.Event) -> None:
        failures = 0
        while not stop.is_set():
            try:
                await self.once()
                failures = 0
            except Exception as exc:  # the request stays; the next look takes it up
                failures += 1
                logger.warning("backup.job_failed", extra={"error": type(exc).__name__})
            wait = min(2.0**failures, MAX_ERROR_WAIT_SECONDS) if failures else POLL_SECONDS
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=wait)

    async def once(self) -> BackupState | None:
        """Take up the oldest request, if any; the state it reached (None: none, or it
        waits because another backup runs)."""
        if self.paused():
            return None
        now = self.clock.now()
        async with self.database.session_factory() as session:
            request = await BackupRunRepository(session).oldest_request(now - REQUEST_GRACE)
        if request is None:
            return None
        outcome = await run_backup(
            self.settings(), self.clock, trigger=BackupTrigger.ADMIN, run_id=request
        )
        if outcome.error_code in WAITING:
            return None
        if outcome.state != BackupState.OK:  # refused before taking it up: end it here
            await self._refused(request, outcome.error_code or "backup.failed")
        logger.info(
            "backup.request_done",
            extra={"run_id": str(request), "state": outcome.state.value},
        )
        return outcome.state

    async def _refused(self, request: uuid.UUID, code: str) -> None:
        """A request still `running` (a backup that failed has ended it already) fails
        with the refusal's code, and the owners hear of it."""
        async with self.database.session_factory() as session, session.begin():
            runs = BackupRunRepository(session)
            run = await runs.get(request)
            if run is None or run.state != BackupState.RUNNING:
                return
            await runs.finish(
                request, state=BackupState.FAILED, at=self.clock.now(), error_code=code
            )
            await tell_managers(session, run.org_id, request)
