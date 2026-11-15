"""`python -m app.ops <area> <command>`: the operations command line (plan M9).

    python -m app.ops backup create [--dir DIR]   # an archive; prints its path
    python -m app.ops backup verify ARCHIVE       # "ok" or one problem code per line
    python -m app.ops backup list [--limit N]     # the recorded backups, newest first

The settings come from the environment like the app's (`HERD_*`); the command line
acts as `system` (audit `via=cli`). Exit status 0 when it worked, 1 when not, 2 for a
wrong command line. Output names files and codes, never content or secrets.
"""

import argparse
from collections.abc import Sequence

from app.core.clock import Clock
from app.core.config import Settings
from app.ops import cli_backup


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="python -m app.ops")
    areas = top.add_subparsers(dest="area", required=True)
    cli_backup.add_commands(areas)
    return top


async def run(argv: Sequence[str], settings: Settings, clock: Clock) -> int:
    try:
        args = parser().parse_args(list(argv))
    except SystemExit as exit_:
        return int(exit_.code or 0)
    status: int = await args.handler(args, settings, clock)
    return status
