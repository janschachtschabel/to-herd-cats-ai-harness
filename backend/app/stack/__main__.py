"""`python -m app.stack init [--secrets DIR] [--db-secret DIR]` (see `app/stack/init.py`)
and `python -m app.stack set-secret-key [--secrets DIR]` (`app/stack/secret_key.py`):
the key from standard input, asked for without echo on a terminal."""

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

from app.stack.init import run_init
from app.stack.secret_key import run_set_secret_key


def main(argv: list[str]) -> int:
    top = argparse.ArgumentParser(prog="python -m app.stack")
    commands = top.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="the stack's secrets and the check of its values")
    init.add_argument("--secrets", type=Path, default=Path("/secrets"))
    init.add_argument("--db-secret", type=Path, default=Path("/db-secret"))
    set_key = commands.add_parser("set-secret-key", help="put a saved HERD_SECRET_KEY back")
    set_key.add_argument("--secrets", type=Path, default=Path("/secrets"))
    args = top.parse_args(argv)
    if args.command == "set-secret-key":
        text = getpass.getpass("HERD_SECRET_KEY: ") if sys.stdin.isatty() else sys.stdin.readline()
        return run_set_secret_key(text, secrets_dir=args.secrets, out=sys.stdout)
    return asyncio.run(
        run_init(os.environ, secrets_dir=args.secrets, db_secret_dir=args.db_secret, out=sys.stdout)
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
