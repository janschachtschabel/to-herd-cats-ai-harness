"""Deleted events stay as tombstones (plan M10 decision 5, task 3b): seen by nobody,
blocking no UID, kept 30 days for sync and feeds, then removed by the due loop's expiry
upkeep (`core/retention.py`, `worker/upkeep.remove_expired`, given its time); a series'
overrides go with it."""

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retention import upkeep_after
from app.modules.calendars.event_models import CalendarEvent
from app.worker.upkeep import remove_expired
from tests.factories import MakeUser
from tests.factories_calendar import logged_in, new_calendar, new_event
from tests.factories_spaces import MakeSpace
from tests.support.clock import SettableClock
from tests.test_event_writes import delete, patch

KEEP = timedelta(days=30)


async def _rows(session: AsyncSession, *ids: str) -> dict[str, CalendarEvent]:
    found = await session.scalars(
        select(CalendarEvent)
        .where(CalendarEvent.id.in_([uuid.UUID(i) for i in ids]))
        .execution_options(populate_existing=True)
    )
    return {str(row.id): row for row in found}


async def test_deleted_events_stay_as_tombstones_for_thirty_days(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    calendar_id = (await new_calendar(client, space.id))["id"]
    kept = await new_event(client, calendar_id, title="Bleibt")
    made = await new_event(client, calendar_id, rrule="FREQ=WEEKLY;COUNT=3")
    override = (
        await patch(
            client, made, title="X", query={"scope": "this", "occurrence": "2026-11-30T10:00:00"}
        )
    ).json()["event"]
    assert (await delete(client, made)).status_code == 204
    rows = await _rows(session, made["id"], override["id"], kept["id"])
    deleted_at = rows[made["id"]].deleted_at
    assert deleted_at is not None and rows[override["id"]].deleted_at is not None
    assert rows[kept["id"]].deleted_at is None
    assert (rows[made["id"]].version, rows[override["id"]].version) == (2, 2)
    assert upkeep_after("calendar_event") == KEEP
    clock = SettableClock(deleted_at + KEEP - timedelta(seconds=1))
    assert await remove_expired(session, "calendar_event", clock.now(), 100) == 0
    clock.advance(timedelta(seconds=2))
    while await remove_expired(session, "calendar_event", clock.now(), 100):
        pass
    assert list(await _rows(session, made["id"], override["id"], kept["id"])) == [kept["id"]]


async def test_a_tombstone_does_not_block_its_uid(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    calendar_id = (await new_calendar(client, space.id))["id"]
    first = await new_event(client, calendar_id, uid="wieder@example.com")
    assert (await delete(client, first)).status_code == 204
    again = await new_event(client, calendar_id, uid="wieder@example.com", title="Neu")
    assert again["id"] != first["id"]
    rows = await _rows(session, first["id"], again["id"])
    assert rows[first["id"]].deleted_at is not None and rows[again["id"]].deleted_at is None
    assert {row.uid for row in rows.values()} == {"wieder@example.com"}
