"""`python -m app.ops <area> <command>`: the operations command line (plan M9).

    python -m app.ops backup create [--dir DIR]   # an archive; prints its path
    python -m app.ops backup verify ARCHIVE       # "ok" or one problem code per line
    python -m app.ops backup list [--limit N]     # the recorded backups, newest first
    python -m app.ops backup run [--scheduled]    # backup, retention, offsite (cron job:
                                                  # --scheduled records trigger schedule)
    python -m app.ops backup schedule             # `run` at every HERD_BACKUP_SCHEDULE term
    python -m app.ops restore check ARCHIVE       # problem codes and warnings, or "ok"
    python -m app.ops restore apply ARCHIVE [--without-secrets]   # empty installation
    python -m app.ops restore apply ARCHIVE --replace --confirm "<organisation name>"
                                                  # in place of the running installation
                                                  # (safety archive, maintenance meanwhile)
    python -m app.ops maintenance status|off      # whether in maintenance; end it

The settings come from the environment like the app's (`HERD_*`); the command line
acts as `system` (audit `via=cli`). Exit status 0 when it worked, 1 when not, 2 for a
wrong command line. Output names files and codes, never content or secrets.
"""

import argparse
from collections.abc import Sequence

from app.core.clock import Clock
from app.core.config import Settings
from app.ops import cli_backup, cli_maintenance, cli_restore


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="python -m app.ops")
    areas = top.add_subparsers(dest="area", required=True)
    cli_backup.add_commands(areas)
    cli_restore.add_commands(areas)
    cli_maintenance.add_commands(areas)
    return top


async def run(argv: Sequence[str], settings: Settings, clock: Clock) -> int:
    try:
        args = parser().parse_args(list(argv))
    except SystemExit as exit_:
        return int(exit_.code or 0)
    status: int = await args.handler(args, settings, clock)
    return status
