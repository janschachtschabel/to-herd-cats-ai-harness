"""`python -m app.ops restore check|apply` (plan M9 tasks 2 and 12): into an empty
installation (`restore.py`), or with `--replace --confirm "<organisation name>"` in
place of a running one (`replace.py`)."""

import argparse
from pathlib import Path
from typing import Any

from app.core.clock import Clock
from app.core.config import Settings
from app.ops import replace
from app.ops.restore import RestoreFailed, RestoreRefused, restore_into_empty
from app.ops.restore_checks import check_restore


def add_commands(areas: Any) -> None:
    restore = areas.add_parser("restore", help="restore an archive")
    commands = restore.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="whether the archive fits this installation")
    check.add_argument("archive", type=Path)
    check.set_defaults(handler=_check)
    apply = commands.add_parser(
        "apply", help="restore the archive (into an empty installation, or --replace)"
    )
    apply.add_argument("archive", type=Path)
    apply.add_argument(
        "--without-secrets",
        action="store_true",
        help="restore although HERD_SECRET_KEY does not fit (enc: values stay unreadable)",
    )
    apply.add_argument(
        "--replace",
        action="store_true",
        help="replace the running installation (safety archive first, maintenance meanwhile)",
    )
    apply.add_argument(
        "--confirm", metavar="NAME", help="with --replace: the organisation's name, exactly"
    )
    apply.set_defaults(handler=_apply)


async def _check(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    check = await check_restore(settings, args.archive)
    for warning in check.warnings:
        print(f"warning {warning}")
    print("\n".join(check.problems) if check.problems else "ok")
    return 1 if check.problems else 0


async def _apply(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    if args.replace:
        return await _replace(args, settings, clock)
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


async def _replace(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    if not args.confirm:
        print("restore.confirm_missing")
        return 1
    try:
        report = await replace.replace_running(
            settings,
            args.archive,
            confirm=args.confirm,
            without_secrets=args.without_secrets,
            clock=clock,
        )
    except RestoreRefused as refused:
        print("\n".join(refused.problems))
        return 1
    except RestoreFailed as failed:
        print(f"failed {failed.code}")
        return 1
    done = report.restore
    print(
        f"replaced by {args.archive.name}: revision {done.revision_from} -> "
        f"{done.revision_to}, {len(done.tables)} tables, {done.files} files; "
        f"safety archive {report.safety_archive.name}"
    )
    return 0
