"""An owner's "Einspielen" (plan M9 task 13): Task 12's replace of the running
installation (`ops/replace.replace_running`, `via` admin), started by the API process
that took the confirmed request, once that request's transaction (its audit entry
`backup.restore_requested`) has committed.

It runs in that process, not as a queued job: a request written down for later could
travel in a backup and be run again by a restored archive; this one exists only while
it runs, at most once. One at a time per process (the runner's claim, taken before the
request's check: `backup.busy`, then `backup.restore_running`); across processes the
schema lock decides (`restore.already_running`). While it runs the whole installation goes into
maintenance (this process's API too), everyone is signed out at the end. When the
process stops, the replace is cancelled: before the swap committed that leaves the old
state whole (`replace._replace`); after it, maintenance stays on
(`python -m app.ops maintenance off`, docs/SICHERUNG.md).

A replace that is refused or fails before maintenance began leaves an audit entry
`backup.restore_failed` (system, the archive, the first code, `via` admin, as the
replace's own) and tells the
owners (`backup.changed`), so the page shows why; failures later are audited by the
replace itself.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import get_database
from app.modules.audit.recorder import record_system
from app.modules.backups.live import tell_managers
from app.modules.backups.repository import BackupRunRepository
from app.ops import replace
from app.ops.restore import RestoreFailed, RestoreRefused

logger = logging.getLogger(__name__)

VIA = "admin"
# Failures after which the database may not hold the old state (`ops/replace.py`).
UNSETTLED = frozenset({"restore.finish_failed", "restore.swap_broken", "restore.swap_unknown"})
Replace = Callable[..., Awaitable[object]]


class ReplaceBusy(Exception):  # noqa: N818 (a verdict)
    """The runner is taken: `backup.busy` (another request is being checked) or
    `backup.restore_running` (a replace runs)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReplaceRunner:
    """At most one replace per process, from the claim on: `claim` looks and takes in
    one synchronous step (no other request runs between them), the claim spans the
    request's check of the archive, and `Claim.start` turns it into the running task.
    Every task started is kept, so `busy` and `stop` see each (review M9b F3)."""

    def __init__(self, run: Replace | None = None) -> None:
        self._run = run
        self._claimed = False
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def busy(self) -> bool:
        return self._claimed or self._running()

    def claim(self) -> "Claim":
        if self._claimed:
            raise ReplaceBusy("backup.busy")
        if self._running():
            raise ReplaceBusy("backup.restore_running")
        self._claimed = True
        return Claim(self)

    async def stop(self) -> None:
        """Cancel every replace under way (the process stops) and wait for each."""
        tasks = [task for task in self._tasks if not task.done()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task

    def _running(self) -> bool:
        return any(not task.done() for task in self._tasks)

    def _launch(self, settings: Settings, archive: Path, confirm: str, clock: Clock) -> None:
        task = asyncio.create_task(self._replace(settings, archive, confirm, clock))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _replace(self, settings: Settings, archive: Path, confirm: str, clock: Clock) -> None:
        run = self._run or replace.replace_running
        try:
            await run(
                settings,
                archive,
                confirm=confirm,
                without_secrets=False,
                clock=clock,
                via=VIA,
                wait=False,
            )
        except RestoreRefused as refused:
            await _record_failure(archive.name, refused.problems)
        except RestoreFailed as failed:
            logger.warning("backup.replace_failed", extra={"code": failed.code})
            if failed.code in UNSETTLED:  # maintenance stays on; the database is the
                return  # archive's, or neither state whole: nothing to record in it now
            await _tell()
        except Exception as exc:
            logger.warning("backup.replace_failed", extra={"error": type(exc).__name__})
            await _record_failure(archive.name, ["restore.failed"])
        else:
            logger.info("backup.replaced", extra={"archive": archive.name})


class Claim:
    """A runner taken by one request: `start` it, or `release` it if the request ends
    without a replace. Either happens once."""

    def __init__(self, runner: ReplaceRunner) -> None:
        self._runner: ReplaceRunner | None = runner

    def start(self, settings: Settings, archive: Path, confirm: str, clock: Clock) -> None:
        runner = self._take()
        runner._launch(settings, archive, confirm, clock)  # noqa: SLF001 (its own claim)

    def release(self) -> None:
        if self._runner is not None:
            self._take()

    def _take(self) -> ReplaceRunner:
        runner, self._runner = self._runner, None
        if runner is None:
            raise RuntimeError("claim used twice")
        runner._claimed = False  # noqa: SLF001 (its own claim)
        return runner


async def _record_failure(archive: str, codes: list[str]) -> None:
    logger.warning("backup.replace_refused", extra={"codes": ",".join(codes)})
    async with get_database().session_factory() as session, session.begin():
        installation = await BackupRunRepository(session).installation()
        if installation is None:
            return
        org_id = installation[0]
        details = {"archive": archive, "code": codes[0] if codes else "restore.failed", "via": VIA}
        await record_system(
            session, org_id, "backup.restore_failed", "organization", org_id, details
        )
        await tell_managers(session, org_id, None)


async def _tell() -> None:
    async with get_database().session_factory() as session, session.begin():
        installation = await BackupRunRepository(session).installation()
        if installation is not None:
            await tell_managers(session, installation[0], None)


_runner = ReplaceRunner()


def replace_runner() -> ReplaceRunner:
    """The process's one runner (the public app's lifespan stops it)."""
    return _runner
