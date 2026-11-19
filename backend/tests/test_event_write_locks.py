"""The write path judges what it locked (review M10 task 3b, R3b-6 and R3b-9): sight is
judged on the row read afresh under its lock, not on the one found before it, and an
override is locked after the series it belongs to *then* (a split meanwhile re-homes
it: the path retries with the new series, so the lock order stays series before
override)."""

import uuid
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_repository import EventRepository
from tests.factories import MakeUser
from tests.factories_calendar import new_event
from tests.factories_spaces import MakeSpace
from tests.test_event_writes import _code, _team, delete, patch

MONDAYS = {
    "starts_at": "2026-11-23T09:00:00+01:00",
    "ends_at": "2026-11-23T10:00:00+01:00",
}


def _after_the_read(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession, stmt: Any
) -> list[uuid.UUID]:
    """Runs `stmt` (another writer's change, committed meanwhile) right after the write
    path found the event by id, before it locks; returns the ids locked, in order."""
    locked: list[uuid.UUID] = []
    find, lock = EventRepository.find, EventRepository.lock

    async def found(self: EventRepository, event_id: uuid.UUID, seen: Any) -> Any:
        event = await find(self, event_id, seen)
        # as another connection would: the row read keeps what it read
        await session.execute(stmt.execution_options(synchronize_session=False))
        return event

    async def locking(self: EventRepository, event_id: uuid.UUID) -> CalendarEvent | None:
        locked.append(event_id)
        return await lock(self, event_id)

    monkeypatch.setattr(EventRepository, "find", found)
    monkeypatch.setattr(EventRepository, "lock", locking)
    return locked


async def test_sight_is_judged_on_the_locked_row(
    make_client: Any,
    make_user: MakeUser,
    make_space: MakeSpace,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The organiser makes the event private between the writer's read and her lock:
    the writer gets 403 `event.private`, never a 409 that tells her the new version."""
    team = await _team(make_client, make_user, make_space)
    made = await new_event(team.organiser_client, team.calendar["id"], **MONDAYS)
    hide = (
        update(CalendarEvent)
        .where(CalendarEvent.id == uuid.UUID(made["id"]))
        .values(visibility="private", version=CalendarEvent.version + 1)
    )
    _after_the_read(monkeypatch, session, hide)

    r = await patch(team.writer_client, made, title="X")

    assert _code(r) == (403, "event.private")
    assert "current_version" not in r.text


async def test_an_override_rehomed_meanwhile_is_locked_after_its_new_series(
    make_client: Any,
    make_user: MakeUser,
    make_space: MakeSpace,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Between the read and the lock a split moves the override to a new series: the
    path locks the new series before the override, and deletes the occurrence there."""
    team = await _team(make_client, make_user, make_space)
    client, calendar_id = team.organiser_client, team.calendar["id"]
    old = await new_event(client, calendar_id, rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS)
    new = await new_event(
        client,
        calendar_id,
        starts_at="2026-11-30T09:00:00+01:00",
        ends_at="2026-11-30T10:00:00+01:00",
        rrule="FREQ=WEEKLY;COUNT=3",
    )
    made = await patch(
        client, old, title="Ausnahme", query={"scope": "this", "occurrence": "2026-11-30T09:00:00"}
    )
    override = made.json()["event"]
    rehome = (
        update(CalendarEvent)
        .where(CalendarEvent.id == uuid.UUID(override["id"]))
        .values(series_id=uuid.UUID(new["id"]), uid=new["uid"])
    )
    locked = _after_the_read(monkeypatch, session, rehome)

    r = await delete(client, override)

    assert r.status_code == 204, r.text
    old_id, new_id, override_id = (uuid.UUID(e["id"]) for e in (old, new, override))
    # The first try (rolled back), the second under the new series, then the delete
    # takes the series it already holds.
    assert locked == [old_id, override_id, new_id, override_id, new_id]
    read = (await client.get(f"/api/events/{new['id']}")).json()
    assert read["exdates"] == ["2026-11-30T09:00:00"]
