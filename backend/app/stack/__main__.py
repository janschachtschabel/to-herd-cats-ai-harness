"""`python -m app.stack init [--secrets DIR] [--db-secret DIR]` (see `app/stack/init.py`)."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from app.stack.init import run_init


def main(argv: list[str]) -> int:
    top = argparse.ArgumentParser(prog="python -m app.stack")
    commands = top.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="the stack's secrets and the check of its values")
    init.add_argument("--secrets", type=Path, default=Path("/secrets"))
    init.add_argument("--db-secret", type=Path, default=Path("/db-secret"))
    args = top.parse_args(argv)
    return asyncio.run(
        run_init(os.environ, secrets_dir=args.secrets, db_secret_dir=args.db_secret, out=sys.stdout)
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
