"""The measurement of the calendar's expansion (plan M10 Task 3c, the gate for Tasks 4 to
9): as a process against a database of its own, through `window.list_window` and the
real route (the public app in this process, over ASGI), and the availability load
shape (the events of 20 people's personal calendars loaded in one statement and
expanded by `expansion.effective`, the shared expansion Task 5 uses).

    uv run python -m scripts.measure_calendar window \
        --database-url postgresql+asyncpg://herd:herd@localhost:5433/herd_measure_x \
        --out run.json [--calls 200] [--extra-calls 50]

The database is migrated and, on its first run, filled (`measure_calendar_seed`);
later runs reuse the stock. Each case first warms up (10 calls, not recorded), then
records each call's duration, its SQL statements (counted on the engine) and, where the
path sees it, the expansion's counted work (`expansion.Budget`: rows × `ROW_WORK` +
rule candidates). Calls rotate over ten windows around the anchor (Monday 23 November
2026, in Europe/Berlin). `scripts/measure_calendar_report.py` judges the file.
"""

import argparse
import asyncio
import json
import logging
import os
import platform
import secrets
import subprocess
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import actor_for
from app.core.actor import Actor
from app.core.db import Database, set_database
from app.core.migrations import upgrade_head
from app.core.pagination import PageParams
from app.core.security import hash_password
from app.modules.auth.context import AuthContext
from app.modules.calendars import expansion
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.window import list_window
from app.modules.users.models import User
from app.web.public import create_public_app
from scripts import measure_calendar_seed as stock_of
from scripts.measure_calendar_report import Call
from scripts.measure_calendar_shapes import busy_times, month_grids, spans, weeks

WARM_UP = 10


class Queries:
    """SQL statements sent through the engine."""

    def __init__(self) -> None:
        self.count = 0

    def hit(self, *_: Any) -> None:
        self.count += 1


type Measured = Callable[[int], Awaitable[Call]]


class Bench:
    def __init__(self, database: Database, queries: Queries) -> None:
        self.database, self.queries = database, queries

    async def record(self, measured: Measured, calls: int) -> list[dict[str, Any]]:
        for i in range(WARM_UP):
            await measured(i)
        return [asdict(await measured(i)) for i in range(calls)]

    async def timed(self, work: Callable[[AsyncSession], Awaitable[Call]]) -> Call:
        before, started = self.queries.count, time.perf_counter()
        async with self.database.session_factory() as session:
            found = await work(session)
            await session.commit()
        ms = (time.perf_counter() - started) * 1000
        return Call(**{**asdict(found), "ms": ms, "queries": self.queries.count - before})

    def window(
        self, actor: Actor, windows: list[tuple[datetime, datetime]], *, every_page: bool
    ) -> Measured:
        async def measured(i: int) -> Call:
            start, end = windows[i % len(windows)]

            async def work(session: AsyncSession) -> Call:
                rows = candidates = items = 0
                cursor = None
                while True:
                    budget = expansion.Budget()
                    page = await list_window(
                        session,
                        actor,
                        start=start,
                        end=end,
                        calendar_ids=None,
                        space_id=None,
                        mine=False,
                        query=None,
                        params=PageParams(limit=100, cursor=cursor),
                        viewer_zone=stock_of.ZONE,
                        budget=budget,
                    )
                    rows, candidates = rows + budget.rows, candidates + budget.counter.candidates
                    items += len(page.items)
                    cursor = page.next_cursor
                    if cursor is None or not every_page:
                        break
                work = rows * expansion.ROW_WORK + candidates
                found = items if every_page else None
                return Call(
                    ms=0, queries=0, work=work, candidates=candidates, rows=rows, occurrences=found
                )

            return await self.timed(work)

        return measured

    def route(self, client: AsyncClient, windows: list[tuple[datetime, datetime]]) -> Measured:
        async def measured(i: int) -> Call:
            start, end = windows[i % len(windows)]
            params: dict[str, str | int] = {
                "from": start.isoformat(),
                "to": end.isoformat(),
                "limit": 100,
                "time_zone": stock_of.ZONE,
            }
            before, started = self.queries.count, time.perf_counter()
            r = await client.get("/api/calendar/events", params=params)
            ms = (time.perf_counter() - started) * 1000
            return Call(ms=ms, queries=self.queries.count - before, status=r.status_code)

        return measured

    def availability(self, org_id: Any, people: dict[Any, Any], days: int) -> Measured:
        windows = spans(days)

        async def measured(i: int) -> Call:
            start, end = windows[i % len(windows)]

            async def work(session: AsyncSession) -> Call:
                busy, spent = await busy_times(session, org_id, people, start, end)
                return Call(
                    ms=0,
                    queries=0,
                    work=sum(b.spent() for b in spent),
                    candidates=sum(b.counter.candidates for b in spent),
                    rows=sum(b.rows for b in spent),
                    occurrences=sum(len(v) for v in busy.values()),
                )

            return await self.timed(work)

        return measured


async def _stock(database: Database) -> stock_of.Stock:
    async with database.engine.begin() as connection:
        await connection.run_sync(upgrade_head)
    async with database.session_factory() as session:
        found = await stock_of.find(session)
        if found is None:
            found = await stock_of.seed(session, hash_password(secrets.token_urlsafe(16)))
            await session.commit()
    return found


async def _client(database: Database, user: User) -> AsyncClient:
    """A signed-in client of the public app; the person's password is a new random one."""
    password = secrets.token_urlsafe(24)
    async with database.session_factory() as session:
        await session.execute(
            update(User).where(User.id == user.id).values(password_hash=hash_password(password))
        )
        await session.commit()
    transport = ASGITransport(app=create_public_app(), raise_app_exceptions=False)
    client = AsyncClient(
        transport=transport, base_url="http://measure", headers={"X-Requested-With": "herd"}
    )
    r = await client.post("/api/auth/login", json={"email": user.email, "password": password})
    if r.status_code != 200:
        raise SystemExit(f"login: {r.status_code}")
    logging.getLogger("app.request").setLevel(logging.WARNING)  # one line per call otherwise
    return client


async def _context(database: Database, head: str) -> dict[str, Any]:
    async with database.session_factory() as session:
        version = await session.scalar(text("SHOW server_version"))
        events = await session.scalar(select(func.count()).select_from(CalendarEvent))
    return {
        "load_average_before": round(os.getloadavg()[0], 2),
        "cpus": os.cpu_count(),
        "python": platform.python_version(),
        "postgres": version,
        "events": events,
        "head": head,
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


async def window(args: argparse.Namespace) -> dict[str, Any]:
    database = Database(args.database_url)
    set_database(database)  # the public app's sessions
    queries = Queries()
    event.listen(database.engine.sync_engine, "before_cursor_execute", queries.hit)
    stock = await _stock(database)
    async with database.session_factory() as session:
        actors = {
            name: await actor_for(session, AuthContext(user=await session.get_one(User, user.id)))
            for name, user in (
                ("viewer", stock.viewer),
                ("idle", stock.idle_viewer),
                ("bound", stock.bound_viewer),
            )
        }
    context = await _context(database, args.head)
    bench, calls, extra = Bench(database, queries), args.calls, args.extra_calls
    client = await _client(database, stock.viewer)
    cases: dict[str, list[dict[str, Any]]] = {}
    plan: list[tuple[str, Measured, int]] = [
        ("week", bench.window(actors["viewer"], weeks(), every_page=False), calls),
        ("week_route", bench.route(client, weeks()), calls),
        ("week_all_pages", bench.window(actors["viewer"], weeks(), every_page=True), extra),
        ("month", bench.window(actors["viewer"], month_grids(), every_page=False), calls),
        ("month_route", bench.route(client, month_grids()), calls),
        ("month_all_pages", bench.window(actors["viewer"], month_grids(), every_page=True), extra),
        ("availability_14", bench.availability(stock.org_id, stock.people, 14), calls),
        ("availability_62", bench.availability(stock.org_id, stock.people, 62), calls),
        ("idle_4001", bench.window(actors["idle"], weeks(), every_page=False), extra),
        ("bound", bench.window(actors["bound"], weeks(), every_page=False), extra),
    ]
    for name, measured, count in plan:
        if args.only and name not in args.only:
            continue
        cases[name] = await bench.record(measured, count)
        print(f"{name}: {len(cases[name])} calls", flush=True)
    await client.aclose()
    context["load_average_after"] = round(os.getloadavg()[0], 2)
    await database.dispose()
    return {"context": context, "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("window", help="measure the window, the route and availability")
    run.add_argument(
        "--database-url", required=True, help="a database of its own, never a shared one"
    )
    run.add_argument("--out", required=True)
    run.add_argument("--calls", type=int, default=200)
    run.add_argument("--extra-calls", type=int, default=50)
    run.add_argument("--only", nargs="*", help="measure only these cases")
    args = parser.parse_args()
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 - git from PATH, as a developer runs it
        capture_output=True,
        text=True,
        check=False,
    )
    args.head = head.stdout.strip()
    measured = asyncio.run(window(args))
    Path(args.out).write_text(json.dumps(measured, indent=1))


if __name__ == "__main__":
    main()
