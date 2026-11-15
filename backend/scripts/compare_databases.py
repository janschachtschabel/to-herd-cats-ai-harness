"""Compare two databases table by table (the restore rehearsal, plan M9 task 2):

    uv run python -m scripts.compare_databases URL_A URL_B [--ignore TABLE ...]

For every table of either database: the row counts, and a checksum of the rows
(md5 over the rows as text, in a fixed order). Prints one line per difference, naming
the table and what differs, never a value; exit 0 when there is none. Passwords
belong in PGPASSWORD-like settings, not on the command line: a URL without one takes
HERD_DATABASE_PASSWORD.
"""

import argparse
import asyncio
import os
import sys
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.db import make_engine


async def figures(url: URL) -> dict[str, tuple[int, str]]:
    engine = make_engine(url)
    try:
        async with engine.connect() as conn:
            return await _figures(conn)
    finally:
        await engine.dispose()


async def _figures(conn: AsyncConnection) -> dict[str, tuple[int, str]]:
    names = (
        await conn.scalars(
            text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
        )
    ).all()
    found = {}
    for name in names:
        quoted = '"' + name.replace('"', '""') + '"'
        row = (
            await conn.execute(
                text(
                    "SELECT count(*), md5(coalesce(string_agg(t::text, chr(10)"  # noqa: S608
                    f" ORDER BY t::text), '')) FROM {quoted} AS t"
                )
            )
        ).one()
        found[name] = (int(row[0]), str(row[1]))
    return found


async def compare(a: URL, b: URL, ignore: Iterable[str] = ()) -> list[str]:
    left, right = await figures(a), await figures(b)
    skip = set(ignore)
    differences = []
    for table in sorted((set(left) | set(right)) - skip):
        if table not in right:
            differences.append(f"{table}: only in A")
        elif table not in left:
            differences.append(f"{table}: only in B")
        elif left[table][0] != right[table][0]:
            differences.append(f"{table}: rows {left[table][0]} != {right[table][0]}")
        elif left[table][1] != right[table][1]:
            differences.append(f"{table}: rows equal, content differs")
    return differences


def _url(raw: str) -> URL:
    url = make_url(raw)
    if url.password is None and (password := os.environ.get("HERD_DATABASE_PASSWORD")):
        url = url.set(password=password)
    return url


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.compare_databases")
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--ignore", nargs="*", default=[])
    args = parser.parse_args(argv)
    differences = await compare(_url(args.a), _url(args.b), args.ignore)
    for line in differences:
        print(line)
    tables = len(await figures(_url(args.a)))
    print(f"compared {tables} tables, {len(differences)} difference(s)")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
