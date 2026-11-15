"""A sprint's dates lie between 2000-01-01 and 2100-12-31 (module review M4b, finding
1): the driver sends `date.max` and `date.min` as `infinity` and `-infinity`, and the
list's order key cannot subtract an infinite date (22008, a 500 for everyone in the
space). The API refuses such a date (422 `sprint.dates_invalid`), the table's CHECK
`dates_range` refuses it from any writer, and the migration that adds the CHECK first
clamps rows an earlier release stored."""

import importlib.util
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories_sprints import close, new_sprint, sprints, start
from tests.factories_tickets import Desk

VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"
OUTSIDE = ("1999-12-31", "2101-01-01", "0001-01-01", "9999-12-31")


async def test_a_date_outside_the_range_is_refused(desk: Desk) -> None:
    url = f"/api/spaces/{desk.space_id}/sprints"
    for starts_on, ends_on in (
        *((day, "2026-11-27") for day in OUTSIDE),
        *(("2026-11-16", day) for day in OUTSIDE),
    ):
        body = {"name": "S", "starts_on": starts_on, "ends_on": ends_on}
        r = await desk.moderator.post(url, json=body)
        assert (r.status_code, r.json()["error"]["code"]) == (422, "sprint.dates_invalid"), body
    sprint = await new_sprint(desk.moderator, desk.space_id, "Rand", "2000-01-01", "2100-12-31")
    for change in (
        {"ends_on": "9999-12-31"},
        {"starts_on": "0001-01-01"},
        {"starts_on": "9999-12-31", "ends_on": "9999-12-31"},
    ):
        r = await desk.moderator.patch(
            f"/api/sprints/{sprint['id']}", json={**change, "version": sprint["version"]}
        )
        assert (r.status_code, r.json()["error"]["code"]) == (422, "sprint.dates_invalid"), change
    sprint = (await start(desk.moderator, sprint)).json()
    assert (await close(desk.moderator, sprint, "backlog")).status_code == 200
    listed = await sprints(desk.viewer, desk.space_id)
    assert [(s["starts_on"], s["ends_on"]) for s in listed] == [("2000-01-01", "2100-12-31")]


async def _insert(session: AsyncSession, desk: Desk, starts_on: str, ends_on: str) -> None:
    await session.execute(
        text(
            "INSERT INTO sprint (id, org_id, space_id, name, goal, starts_on, ends_on, state,"
            " version) SELECT gen_random_uuid(), org_id, id, 'S', '', CAST(CAST(:a AS text) AS date),"
            " CAST(CAST(:b AS text) AS date), 'planned', 1 FROM space WHERE id = :space"
        ),
        {"a": starts_on, "b": ends_on, "space": desk.space_id},
    )


@pytest.mark.parametrize(
    ("starts_on", "ends_on"),
    [
        ("2026-11-16", "infinity"),
        ("-infinity", "2026-11-27"),
        ("1999-12-31", "2026-11-27"),
        ("2026-11-16", "2101-01-01"),
    ],
)
async def test_the_table_refuses_a_date_outside_the_range(
    desk: Desk, session: AsyncSession, starts_on: str, ends_on: str
) -> None:
    with pytest.raises(IntegrityError, match="ck_sprint_dates_range"):
        async with session.begin_nested():
            await _insert(session, desk, starts_on, ends_on)


def _migration() -> ModuleType:
    (path,) = VERSIONS.glob("*_m4bfix_sprint_dates.py")
    spec = importlib.util.spec_from_file_location("m4bfix_sprint_dates", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade(connection: Connection) -> None:
    with Operations.context(MigrationContext.configure(connection)):
        _migration().upgrade()


async def test_the_migration_clamps_what_an_earlier_release_stored(
    desk: Desk, session: AsyncSession
) -> None:
    """Run in the test's transaction: the CHECK dropped (as before the migration), rows
    an earlier release could store, then the migration's upgrade."""
    await session.execute(text("ALTER TABLE sprint DROP CONSTRAINT ck_sprint_dates_range"))
    for starts_on, ends_on in (
        ("2026-12-01", "infinity"),
        ("-infinity", "-infinity"),
        ("0001-01-01", "2026-01-31"),
        ("2026-11-16", "2026-11-27"),
    ):
        await _insert(session, desk, starts_on, ends_on)
    connection = await session.connection()
    await connection.run_sync(_upgrade)
    rows = await session.execute(
        text("SELECT starts_on, ends_on, version FROM sprint ORDER BY starts_on, ends_on")
    )
    assert [tuple(row) for row in rows] == [
        (date(2000, 1, 1), date(2000, 1, 1), 2),
        (date(2000, 1, 1), date(2026, 1, 31), 2),
        (date(2026, 11, 16), date(2026, 11, 27), 1),
        (date(2026, 12, 1), date(2100, 12, 31), 2),
    ]
    with pytest.raises(IntegrityError, match="ck_sprint_dates_range"):
        async with session.begin_nested():
            await _insert(session, desk, "2026-11-16", "infinity")
