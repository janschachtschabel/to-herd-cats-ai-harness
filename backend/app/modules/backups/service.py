"""Backups in the administration (plan M9 task 13, decisions 9 to 11): only with
`backup.manage` (owners); anyone else is answered like an unknown backup (404
`backup.not_found`, `guard.py`). Every start, download, upload, check and replace is
audited with the person as actor, names and figures only.

- `runs`: the `backup_run` rows, newest first, paginated.
- `request`: "Jetzt sichern": a `running` row with trigger `admin` that a worker takes
  up (`jobs.py`); refused while a backup runs or waits (409 `backup.already_running`).
  "Jetzt sichern" and "Einspielen" take one claim for their first transaction (409
  `backup.busy` while another request holds it), so two at once start one.
- `archives`, `download`, `upload`: the archives in HERD_BACKUP_DIR (`archives.py`).
- `check`: an archive against the installation (`checking.py`).
- `replace`: the organisation's exact name (422 `backup.confirm_mismatch`), no backup
  running, no replace under way or being started in this process (409
  `backup.restore_running`, or `backup.busy` while another request checks; the
  runner's claim spans the check), and a clean check (409 `backup.replace_refused`
  with the problems); then, after the commit, the replace in this process
  (`replacing.py`).
- `last_restore`: the newest attempt from the audit log.

A transfer (upload, check) ends the request's transaction first: no database
connection waits on a slow line or a long read.
"""

import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.clock import SYSTEM_CLOCK, Clock
from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import (
    Page,
    decode_cursor,
    decode_key_cursor,
    encode_cursor,
    encode_key_cursor,
)
from app.modules.audit.recorder import record
from app.modules.audit.repository import AuditRepository
from app.modules.backups import archives
from app.modules.backups.archives import ArchiveFile, ArchiveInvalid
from app.modules.backups.checking import CheckReport, check_archive
from app.modules.backups.guard import require_backup_manage
from app.modules.backups.live import tell_managers
from app.modules.backups.models import BackupRun, BackupTrigger
from app.modules.backups.replacing import ReplaceBusy, replace_runner
from app.modules.backups.repository import BackupRunRepository
from app.modules.backups.schemas import RestoreAttemptOut

CLOCK: Clock = SYSTEM_CLOCK  # tests set one of their own
REQUESTED, FAILED = "backup.restore_requested", "backup.restore_failed"
_NO_ID = uuid.UUID(int=0)


class BackupAdmin:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.runs_repo = BackupRunRepository(session)

    async def runs(self, actor: Actor, limit: int, cursor: str | None) -> Page[BackupRun]:
        await require_backup_manage(self.session, actor)
        after = decode_cursor(cursor) if cursor else None
        rows = await self.runs_repo.page(actor.org_id, limit, after)
        more = len(rows) > limit
        rows = rows[:limit]
        last = rows[-1] if more else None
        return Page[BackupRun](
            items=rows, next_cursor=encode_cursor(last.started_at, last.id) if last else None
        )

    async def request(self, actor: Actor) -> BackupRun:
        await require_backup_manage(self.session, actor)
        await self._claim()
        if await self.runs_repo.any_running(actor.org_id):
            raise Conflict(code="backup.already_running")
        run = await self.runs_repo.start(actor.org_id, BackupTrigger.ADMIN, CLOCK.now())
        await record(self.session, actor, "backup.requested", "backup_run", run.id)
        await tell_managers(self.session, actor.org_id, run.id)
        return run

    async def archives(self, actor: Actor, limit: int, cursor: str | None) -> Page[ArchiveFile]:
        await require_backup_manage(self.session, actor)
        after = decode_key_cursor(cursor)[0] if cursor else None
        found = archives.page_after(archives.archive_files(self.settings.backup_dir), after, limit)
        more = len(found) > limit
        found = found[:limit]
        last = encode_key_cursor(found[-1].name, _NO_ID) if more else None
        return Page[ArchiveFile](items=found, next_cursor=last)

    async def download(self, actor: Actor, name: str) -> ArchiveFile:
        archive = await self._archive(actor, name)
        await self._audit(actor, "backup.downloaded", archive, bytes=archive.size)
        return archive

    async def upload(self, actor: Actor, body: AsyncIterator[bytes]) -> ArchiveFile:
        await require_backup_manage(self.session, actor)
        await self.session.commit()  # no connection waits for the upload
        try:
            archive = await archives.receive(
                self.settings.backup_dir,
                body,
                max_bytes=self.settings.backup_upload_max_bytes,
                read_timeout=self.settings.body_read_timeout_seconds,
                at=CLOCK.now(),
            )
        except ArchiveInvalid as invalid:
            raise ValidationFailed(
                "Not a good backup archive",
                code="backup.archive_invalid",
                details={"problems": invalid.problems},
            ) from None
        await self._audit(actor, "backup.uploaded", archive, bytes=archive.size)
        return archive

    async def check(self, actor: Actor, name: str) -> CheckReport:
        archive = await self._archive(actor, name)
        await self.session.commit()  # the archive is read back without a connection
        report = await check_archive(self.session, self.settings, archive.path)
        await self._audit(actor, "backup.checked", archive, problems=report.problems)
        return report

    async def replace(self, actor: Actor, name: str, confirm: str) -> ArchiveFile:
        archive = await self._archive(actor, name)
        installation = await self.runs_repo.installation()
        if installation is None or installation[1] != confirm:
            raise ValidationFailed(
                "The organisation's name does not match", code="backup.confirm_mismatch"
            )
        await self._claim()
        if await self.runs_repo.any_running(actor.org_id):
            raise Conflict(code="backup.already_running")
        try:  # no await between the look and the claim: one step in this process
            claim = replace_runner().claim()
        except ReplaceBusy as busy:
            raise Conflict(code=busy.code) from None
        try:
            await self.session.commit()
            report = await check_archive(self.session, self.settings, archive.path)
            if report.problems:
                raise Conflict(code="backup.replace_refused", details={"problems": report.problems})
            await self._audit(actor, REQUESTED, archive)
            await tell_managers(self.session, actor.org_id, None)
            await self.session.commit()  # the request is audited before the replace runs
        except BaseException:
            claim.release()
            raise
        claim.start(self.settings, archive.path, confirm, CLOCK)
        return archive

    async def last_restore(self, actor: Actor) -> RestoreAttemptOut | None:
        await require_backup_manage(self.session, actor)
        entry = await AuditRepository(self.session).latest_of(actor.org_id, (REQUESTED, FAILED))
        if entry is None:
            return None
        details = entry.details or {}
        return RestoreAttemptOut(
            state="failed" if entry.action == FAILED else "requested",
            at=entry.created_at,
            archive_name=details.get("archive"),
            code=details.get("code"),
        )

    async def _claim(self) -> None:
        if not await self.runs_repo.claim_admin():
            raise Conflict(code="backup.busy")

    async def _archive(self, actor: Actor, name: str) -> ArchiveFile:
        await require_backup_manage(self.session, actor)
        archive = archives.find(self.settings.backup_dir, name)
        if archive is None:
            raise NotFound(code="backup.not_found")
        return archive

    async def _audit(
        self, actor: Actor, action: str, archive: ArchiveFile, **figures: object
    ) -> None:
        details = {"archive": archive.name, **figures}
        await record(self.session, actor, action, "organization", actor.org_id, details)
