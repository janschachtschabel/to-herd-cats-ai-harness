"""`python -m app.ops maintenance status|off` (plan M9 task 12). A replace turns
maintenance on and off itself; `off` is for a replace that stopped after the swap
and left it on (`docs/SICHERUNG.md`), once the database is ready to serve again.
Acts as `system` (audit `maintenance.ended`, `via=cli`)."""

import argparse
from datetime import UTC
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import make_engine
from app.modules.maintenance.service import MaintenanceService


def add_commands(areas: Any) -> None:
    maintenance = areas.add_parser("maintenance", help="the installation's maintenance mode")
    commands = maintenance.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="whether the installation is in maintenance")
    status.set_defaults(handler=_status)
    off = commands.add_parser("off", help="end maintenance (after a replace that stopped)")
    off.set_defaults(handler=_off)


async def _status(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    engine = make_engine(settings.database())
    try:
        async with async_sessionmaker(engine)() as session:
            state = await MaintenanceService(session).state()
    finally:
        await engine.dispose()
    if not state.active or state.reason is None or state.started_at is None:
        print("off")
    else:
        since = state.started_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"on {state.reason.value} since {since}")
    return 0


async def _off(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    engine = make_engine(settings.database())
    try:
        async with async_sessionmaker(engine)() as session:
            ended = await MaintenanceService(session).end_all(via="cli")
            await session.commit()
    finally:
        await engine.dispose()
    print("off" if ended else "off (was off)")
    return 0
