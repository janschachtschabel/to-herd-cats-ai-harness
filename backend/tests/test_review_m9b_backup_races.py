"""Review M9b, findings F2 and F3: the administration's "Jetzt sichern" and
"Einspielen" check "is one running?" and then write, with nothing in between that
makes the two one step; two requests at the same time both pass."""

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.backups.models import BackupRun, BackupState
from app.modules.backups.replacing import replace_runner
from app.modules.backups.repository import BackupRunRepository
from tests.factories import login
from tests.factories_restore import make_archive, source_settings
from tests.real_db import MakeRealClient, RealDb


async def _no_problem(conn: object) -> None:
    return None


async def test_two_requests_at_once_make_one_backup_request(
    real_db: RealDb, make_real_client: MakeRealClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`service.request`: "refused while a backup runs or waits (409
    `backup.already_running`)". Two owners (or one double click through two tabs).
    Both looks are held until the other has looked too (or a second passed: a fix
    that makes the second request wait for the first must not hang here)."""
    looked = 0
    both = asyncio.Event()
    look = BackupRunRepository.any_running

    async def look_together(self: BackupRunRepository, org_id: Any) -> bool:
        nonlocal looked
        found = await look(self, org_id)
        looked += 1
        if looked >= 2:
            both.set()
        with suppress(TimeoutError):
            await asyncio.wait_for(both.wait(), timeout=1)
        return found

    monkeypatch.setattr(BackupRunRepository, "any_running", look_together)
    first, second = await make_real_client(), await make_real_client()
    await login(first, real_db.owner_email)
    await login(second, real_db.owner_email)

    answers = await asyncio.gather(first.post("/api/backups"), second.post("/api/backups"))

    async with real_db.database.session_factory() as session:
        waiting = (
            await session.scalars(select(BackupRun).where(BackupRun.state == BackupState.RUNNING))
        ).all()
    assert sorted(a.status_code for a in answers) == [202, 409]
    assert len(waiting) == 1


async def test_two_replaces_at_once_start_one(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`replacing.py`: "One at a time per process". Both requests find the runner idle
    (the check of the archive lies between the look and the start), both start a
    replace, and the runner knows only the second: `busy` and `stop` (the process's
    shutdown) no longer see the first."""
    archive = await make_archive(source_settings(tmp_path, data_dir))
    monkeypatch.setattr(get_settings(), "backup_dir", archive.parent)
    # A superuser test role is refused before the claim (review M9b F2-1).
    monkeypatch.setattr("app.modules.backups.service.superuser_problem", _no_problem)
    release = asyncio.Event()
    started: list[Path] = []

    async def slow(settings: Any, archive: Path, **kwargs: Any) -> None:
        started.append(archive)
        await release.wait()

    runner = replace_runner()
    monkeypatch.setattr(runner, "_run", slow)
    first, second = await make_real_client(), await make_real_client()
    me = await login(first, real_db.owner_email)
    await login(second, real_db.owner_email)
    path = f"/api/backups/archives/{archive.name}/replace"
    body = {"confirm": me["org"]["name"]}
    try:
        answers = await asyncio.gather(first.post(path, json=body), second.post(path, json=body))
        await asyncio.sleep(0.2)  # the started tasks reach `slow`
        assert sorted(a.status_code for a in answers) == [202, 409]
        assert len(started) == 1
    finally:
        release.set()
        await asyncio.sleep(0.1)
        await runner.stop()
