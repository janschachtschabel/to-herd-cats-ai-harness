"""`python -m app.stack init [--secrets DIR] [--db-secret DIR]` (see `app/stack/init.py`),
`python -m app.stack set-secret-key [--secrets DIR]` (`app/stack/secret_key.py`): the
key from standard input, asked for without echo on a terminal, and `python -m
app.stack db-owner` (`app/stack/db_owner.py`): the app's database role, made by the
superuser, whose password comes from `--superuser-password-file` or, without it, from
the environment variable HERD_DB_SUPERUSER_PASSWORD."""

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

from app.stack.db_owner import OwnerSetup, run_db_owner
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
    owner = commands.add_parser("db-owner", help="the app's database role, no superuser")
    owner.add_argument("--host", default="db")
    owner.add_argument("--port", type=int, default=5432)
    owner.add_argument("--database", default="herd")
    owner.add_argument("--superuser", default="herd")
    owner.add_argument("--superuser-password-file", type=Path)
    owner.add_argument("--owner", default="herd_owner")
    owner.add_argument(
        "--owner-password-file", type=Path, default=Path("/secrets/db_owner_password")
    )
    args = top.parse_args(argv)
    if args.command == "db-owner":
        return asyncio.run(run_db_owner(_owner_setup(args), out=sys.stdout))
    if args.command == "set-secret-key":
        text = getpass.getpass("HERD_SECRET_KEY: ") if sys.stdin.isatty() else sys.stdin.readline()
        return run_set_secret_key(text, secrets_dir=args.secrets, out=sys.stdout)
    return asyncio.run(
        run_init(os.environ, secrets_dir=args.secrets, db_secret_dir=args.db_secret, out=sys.stdout)
    )


def _owner_setup(args: argparse.Namespace) -> OwnerSetup:
    if args.superuser_password_file is not None:
        password = args.superuser_password_file.read_text(encoding="utf-8").strip()
    else:
        password = os.environ.get("HERD_DB_SUPERUSER_PASSWORD", "")
    return OwnerSetup(
        host=args.host,
        port=args.port,
        database=args.database,
        superuser=args.superuser,
        superuser_password=password,
        owner=args.owner,
        owner_password_file=args.owner_password_file,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
