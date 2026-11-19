"""What a series operation does to its overrides beyond moving them (review M10 task
3b, R3b-1 and R3b-2).

- `require_full_sight`: every override an operation writes (drops, deletes, moves,
  re-homes or changes) needs the writer's full sight, as the series itself does
  (decision 3, C2): with "busy" sight of any of them the whole operation is 403
  `event.private`, saying nothing about which one; a dry run answers the same. Whether
  admin power alone showed one of them (the write is then audited).
- `spread`: a content change of a series reaches each override field whose value
  still equals the series' old value (what the override did not change itself);
  making the series private, or cancelling it, reaches every override.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from app.core.actor import Actor
from app.modules.calendars import sight
from app.modules.calendars.event_models import CalendarEvent, EventStatus, EventVisibility
from app.modules.calendars.event_writes import private
from app.modules.calendars.sight import Sight

# Values a series' change gives every override, whatever the override holds.
EVERYWHERE = {"visibility": EventVisibility.PRIVATE, "status": EventStatus.CANCELLED}


def require_full_sight(actor: Actor, overrides: Iterable[CalendarEvent]) -> bool:
    """403 `event.private` unless the actor sees each override in full (on the named
    way, as a writer of their space); whether admin power alone shows any."""
    by_power = False
    for override in overrides:
        attends = sight.attends(actor, override)
        found = sight.of(actor, override, reads=True, attends=attends, named=True)
        if found is not Sight.FULL:
            raise private()
        by_power = by_power or sight.by_admin_power(
            actor, override, reads=True, attends=attends, named=True
        )
    return by_power


def spread(
    before: Mapping[str, Any], content: Mapping[str, Any], overrides: Sequence[CalendarEvent]
) -> list[tuple[CalendarEvent, dict[str, Any]]]:
    """For each override the content change reaches, the values it takes: `before`
    holds the series' content before the change, `content` what the change names."""
    reached = []
    for override in overrides:
        values = {
            name: new
            for name, new in content.items()
            if getattr(override, name) != new
            and (getattr(override, name) == before[name] or EVERYWHERE.get(name) == new)
        }
        if values:
            reached.append((override, values))
    return reached


def apply(reached: Sequence[tuple[CalendarEvent, Mapping[str, Any]]]) -> None:
    for override, values in reached:
        for name, value in values.items():
            setattr(override, name, value)
        override.version += 1
