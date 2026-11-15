"""`python -m app.ops backup create|verify|list` (plan M9 task 1)."""

import argparse
import asyncio
import signal
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import make_engine
from app.modules.backups.models import BackupRun, BackupState, BackupTrigger, OffsiteState
from app.modules.backups.repository import BackupRunRepository
from app.ops.archive import verify_archive
from app.ops.backup import create_backup
from app.ops.cli_run import run_backup
from app.ops.schedule import run_schedule

LIST_COLUMNS = (
    "started",
    "finished",
    "trigger",
    "state",
    "bytes",
    "sha256",
    "archive",
    "error",
    "offsite",
)


def add_commands(areas: Any) -> None:
    backup = areas.add_parser("backup", help="backup archives")
    commands = backup.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="write an archive of the installation")
    create.add_argument("--dir", type=Path, help="directory (default HERD_BACKUP_DIR)")
    create.set_defaults(handler=_create)
    verify = commands.add_parser("verify", help="read an archive back and check it")
    verify.add_argument("archive", type=Path)
    verify.set_defaults(handler=_verify)
    run = commands.add_parser("run", help="a backup, retention and offsite (the cron job)")
    run.set_defaults(handler=_run)
    schedule = commands.add_parser(
        "schedule", help="back up at every term of HERD_BACKUP_SCHEDULE until stopped"
    )
    schedule.set_defaults(handler=_schedule)
    listing = commands.add_parser("list", help="the recorded backups, newest first")
    listing.add_argument("--limit", type=int, default=20)
    listing.set_defaults(handler=_list)


async def _create(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    if args.dir is not None:
        settings = settings.model_copy(update={"backup_dir": args.dir})
    outcome = await create_backup(settings, trigger=BackupTrigger.CLI, clock=clock)
    if outcome.state != BackupState.OK or outcome.archive is None:
        print(f"failed {outcome.error_code}")
        return 1
    print(outcome.archive)
    return 0


async def _run(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    outcome = await run_backup(settings, clock, trigger=BackupTrigger.SCHEDULE)
    if outcome.state != BackupState.OK:
        print(f"failed {outcome.error_code}")
        return 1
    print(f"{outcome.archive} offsite={outcome.offsite.value}")
    return 1 if outcome.offsite == OffsiteState.FAILED else 0


async def _schedule(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    await run_schedule(settings, clock, stop=stop)
    return 0


async def _verify(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    problems = verify_archive(args.archive)
    print("\n".join(problems) if problems else "ok")
    return 1 if problems else 0


async def _list(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    engine = make_engine(settings.database())
    try:
        async with async_sessionmaker(engine)() as session:
            runs = BackupRunRepository(session)
            org_id = await runs.installation_org()
            rows = await runs.latest(org_id, max(1, min(args.limit, 1000))) if org_id else []
    finally:
        await engine.dispose()
    print("\t".join(LIST_COLUMNS))
    for row in rows:
        print("\t".join(_cells(row)))
    return 0


def _cells(run: BackupRun) -> list[str]:
    return [
        _time(run.started_at),
        _time(run.finished_at),
        run.trigger,
        run.state,
        str(run.bytes) if run.bytes is not None else "-",
        run.archive_sha256[:12] if run.archive_sha256 else "-",
        run.archive or "-",
        run.error_code or "-",
        run.offsite_state,
    ]


def _time(at: datetime | None) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if at is not None else "-"
