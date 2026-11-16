"""Shared by the replace tests (plan M9 task 12): the running installation is a
scratch database (`target`) that an archive of the committed test database was
restored into, then changed (`MARK`), so that its present state differs from the
archive."""

from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.core.db import make_engine
from app.ops.restore import restore_into_empty
from tests.factories_restore import AT, Target
from tests.support.clock import SettableClock

NAME = "Real Org"  # the organisation of `real_db`
MARK = "Nach der Sicherung"


async def running(target: Target, archive: Path) -> None:
    """The target as a running installation: the archive restored, then changed."""
    await restore_into_empty(
        target.settings, archive, without_secrets=False, clock=SettableClock(AT)
    )
    await sql(
        target.settings,
        "INSERT INTO user_group (id, org_id, name, version)"
        f" SELECT gen_random_uuid(), id, '{MARK}', 1 FROM organization",
    )


async def sql(settings: Settings, statement: str) -> None:
    engine = make_engine(settings.database())
    try:
        async with engine.begin() as conn:
            await conn.execute(text(statement))
    finally:
        await engine.dispose()


async def scalar(settings: Settings, statement: str) -> object:
    engine = make_engine(settings.database())
    try:
        async with engine.connect() as conn:
            return await conn.scalar(text(statement))
    finally:
        await engine.dispose()


async def rows(settings: Settings, stmt):  # type: ignore[no-untyped-def]
    engine = make_engine(settings.database())
    try:
        async with engine.connect() as conn:
            return (await conn.execute(stmt)).all()
    finally:
        await engine.dispose()


async def marked(settings: Settings) -> int:
    return int(
        await scalar(settings, f"SELECT count(*) FROM user_group WHERE name = '{MARK}'") or 0
    )


def printed(capsys: pytest.CaptureFixture[str]) -> str:
    """What the command printed (the log lines, JSON, left out)."""
    out = capsys.readouterr().out.splitlines()
    return "\n".join(line for line in out if not line.startswith("{"))
