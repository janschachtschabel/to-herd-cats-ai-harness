"""Splitting a series at an occurrence (plan M10 decision 6, I5): `scope=following`.

- Where: `series_cut.cut`. The new part starts at the **anchor**, the first occurrence
  from the split on that can start a series keeping its pattern (one the rule names,
  not in a clock-change gap; review M10 task 3b, R3b-3 and R3b-4), with a UID of its
  own, the old one's content and organiser (then the change), and its rule written
  out (a counted rule keeps the rest, so the total stays). The old part ends just
  before the anchor (`UNTIL`, also in place of a `COUNT`). RDATEs, EXDATEs and
  overrides from the anchor on move to the new part (along with its start if the
  change moves it, `series_rebase.rebase`). Occurrences from the split up to the
  anchor (an RDATE, a gap occurrence: **strays**) stay with the old part and take the
  change as overrides of it, at the wall time the rule names them by.
- The change names the split occurrence's times (ruling 6); at the anchor and at each
  stray it does the same (`series_effect`).
- The content of the change reaches the overrides from the split on as `scope=all`
  reaches a series' overrides (`series_reach.spread`); `CARRY` copies what hangs on
  the series to the new part (Task 4: attendees and their answers, Task 6: reminders).
- A change that names a rule of its own starts the new part at the split occurrence
  itself; nothing is left to keep.
- Splitting at the first live occurrence is `scope=all` (the caller decides that).
- `truncate` (deleting this and the following) ends the old series the same way and
  makes its overrides from the split on tombstones.
- `Edited.reached` names every existing override the split writes (R3b-1).
"""

import dataclasses
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_repository import EventRepository
from app.modules.calendars.event_times import Checked, Times, check, times_of, wall_start
from app.modules.calendars.event_writes import (
    CONTENT_FIELDS,
    CREATED,
    UPDATED,
    Change,
    announce,
    changed_fields,
    new_uid,
    snapshot,
    stored_names,
    tombstone,
)
from app.modules.calendars.recurrence import Series
from app.modules.calendars.series import Edited, add_override
from app.modules.calendars.series_cut import Cut, cut
from app.modules.calendars.series_effect import effect_of, moved_to, occurrence_after
from app.modules.calendars.series_reach import apply, spread
from app.modules.calendars.series_rebase import (
    Dropped,
    Rebased,
    move_overrides,
    occurrence_times,
    rebase,
    safely,
    store_times,
    stored_series,
)

# What hangs on a series and goes along to the part split off: (session, old, new).
type Carry = Callable[[AsyncSession, CalendarEvent, CalendarEvent], Awaitable[None]]
CARRY: list[Carry] = []


def _old_part(event: CalendarEvent, part: Series, zone: str) -> Checked:
    times = dataclasses.replace(
        times_of(event), rrule=part.rrule, rdates=part.rdates, exdates=part.exdates
    )
    return check(times, zone)


def _new_base(series: Series, part: Series) -> Times:
    return dataclasses.replace(
        occurrence_times(series, part.start),
        rrule=part.rrule,
        rdates=part.rdates,
        exdates=part.exdates,
    )


def _unique(events: Sequence[CalendarEvent]) -> tuple[CalendarEvent, ...]:
    return tuple({event.id: event for event in events}.values())


async def split(
    session: AsyncSession,
    actor: Actor,
    event: CalendarEvent,
    wall: datetime,
    change: Change,
    *,
    dry_run: bool,
) -> Edited:
    """Splits the series `event` at its occurrence `wall` (not its first live one); the
    answer shows the new part (without one: the split occurrence's override)."""
    repo = EventRepository(session, event.org_id)
    zone = await repo.calendar_zone(event.calendar_id)
    series = stored_series(event)
    keep = "rrule" not in change.values
    parts: Cut = safely(lambda: cut(series, wall, keep_pattern=keep))
    effect = effect_of(series, wall, change.values, zone)
    old = _old_part(event, parts.old, zone)
    later = await repo.overrides_of(event.id, since=wall)
    anchor = parts.anchor
    carried = [o for o in later if anchor is not None and (o.recurrence_id or wall) >= anchor]
    staying = [o for o in later if o not in carried]
    rebased: Rebased | None = None
    if parts.new is not None and anchor is not None:
        base = _new_base(series, parts.new)
        values = moved_to(series, wall, change.values, anchor, zone)
        rebased = rebase(base, wall_start(base, zone), values, carried, zone)
    orphans = carried if rebased is None else []  # overrides of deleted occurrences
    before = snapshot(event)
    kept = [*staying, *(o for o, _ in (rebased.moved if rebased else []))]
    spreading = spread(before, change.content(), kept)
    reached = _unique(
        [*(rebased.written(rehomed=True) if rebased else []), *orphans, *(o for o, _ in spreading)]
    )
    taken = {o.recurrence_id for o in staying}
    strays = {
        r: check(occurrence_after(series, effect, r), zone)
        for r in parts.strays
        if r not in taken and change.values
    }
    counts = rebased.counts() if rebased else Dropped()
    if dry_run:
        return Edited(event, [], counts, reached, wrote=False)
    new: CalendarEvent | None = None
    if rebased is not None:
        content = {name: getattr(event, name) for name in CONTENT_FIELDS} | change.content()
        new = CalendarEvent(
            org_id=event.org_id,
            calendar_id=event.calendar_id,
            space_id=event.space_id,
            uid=new_uid(),
            organizer_type=event.organizer_type,
            organizer_id=event.organizer_id,
            version=1,
            **content,
        )
        store_times(new, rebased.checked)
        await repo.add(new)  # a new UID is free
    store_times(event, old)
    fields = changed_fields(before, event)
    if not (new or fields or reached or strays):
        return Edited(event, [], counts, (), wrote=False)
    event.version += 1
    await session.flush()
    if rebased is not None:
        await move_overrides(session, rebased, to=new)
    for orphan in orphans:
        tombstone(orphan)
    apply(spreading)
    added = [await add_override(session, actor, event, r, change, t) for r, t in strays.items()]
    if new is not None:
        for carry in CARRY:
            await carry(session, event, new)
    await announce(session, actor, event, UPDATED, fields, overrides=reached)
    if new is not None:
        await announce(session, actor, new, CREATED)
    at_split = next((o for o in [*added, *staying] if o.recurrence_id == wall), event)
    return Edited(new or at_split, stored_names(change.values), counts, reached)


async def truncate(
    session: AsyncSession, actor: Actor, event: CalendarEvent, wall: datetime
) -> Edited:
    """Deletes the occurrence `wall` (not the first live one) and every later one."""
    repo = EventRepository(session, event.org_id)
    zone = await repo.calendar_zone(event.calendar_id)
    stored = stored_series(event)
    parts = safely(lambda: cut(stored, wall, keep_pattern=False))
    old = _old_part(event, parts.old, zone)
    reached = tuple(await repo.overrides_of(event.id, since=wall))
    for override in reached:
        tombstone(override)
    before = snapshot(event)
    store_times(event, old)
    event.version += 1
    await session.flush()
    fields = changed_fields(before, event)
    await announce(session, actor, event, UPDATED, fields, overrides=reached)
    return Edited(event, fields, reached=reached)
