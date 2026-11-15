"""`python -m app.ops restore check|apply` (plan M9 task 2): into an empty
installation only (`restore.py`)."""

import argparse
from pathlib import Path
from typing import Any

from app.core.clock import Clock
from app.core.config import Settings
from app.ops.restore import RestoreFailed, RestoreRefused, restore_into_empty
from app.ops.restore_checks import check_restore


def add_commands(areas: Any) -> None:
    restore = areas.add_parser("restore", help="restore an archive into an empty installation")
    commands = restore.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="whether the archive fits this installation")
    check.add_argument("archive", type=Path)
    check.set_defaults(handler=_check)
    apply = commands.add_parser("apply", help="restore the archive (empty installation only)")
    apply.add_argument("archive", type=Path)
    apply.add_argument(
        "--without-secrets",
        action="store_true",
        help="restore although HERD_SECRET_KEY does not fit (enc: values stay unreadable)",
    )
    apply.set_defaults(handler=_apply)


async def _check(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    check = await check_restore(settings, args.archive)
    for warning in check.warnings:
        print(f"warning {warning}")
    print("\n".join(check.problems) if check.problems else "ok")
    return 1 if check.problems else 0


async def _apply(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    try:
        report = await restore_into_empty(
            settings, args.archive, without_secrets=args.without_secrets, clock=clock
        )
    except RestoreRefused as refused:
        print("\n".join(refused.problems))
        return 1
    except RestoreFailed as failed:
        print(f"failed {failed.code}")
        return 1
    print(
        f"restored {args.archive.name}: revision {report.revision_from} -> "
        f"{report.revision_to}, {len(report.tables)} tables, {report.files} files"
    )
    return 0
