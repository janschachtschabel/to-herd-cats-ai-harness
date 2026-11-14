"""A schedule as the API takes it, checked and turned into an automation's columns and
its next terms (plan M7 decisions 4 and 5): pure, no database (the tag of an event
rule's filter is the service's to check), "now" from the caller.

- `once`: an instant after now (else 422 `automation.in_the_past`).
- `recurring`: cron and IANA zone, no two of the next five terms closer than 15
  minutes (`terms.check_recurring`).
- `heartbeat`: interval and active hours (`heartbeat_terms.check`).
- `event`: no terms; filters only with `ticket.created` (422
  `automation.invalid_filter`).

Refusals are 422 with the term check's code. The preview is the next five terms (a
`once`: its instant; an event rule: none); `upcoming` gives them for a stored row.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.errors import ValidationFailed
from app.modules.automations import heartbeats
from app.modules.automations.heartbeat_terms import Hours, check, next_heartbeat
from app.modules.automations.models import Automation, AutomationKind, AutomationState, EventType
from app.modules.automations.schemas import EventIn, HeartbeatIn, OnceIn, RecurringIn
from app.modules.automations.terms import PREVIEW_TERMS, TermError, check_recurring, upcoming

Schedule = OnceIn | RecurringIn | HeartbeatIn | EventIn

# The schedule's columns, all of them for every kind (those of other kinds empty).
COLUMNS = (
    "cron",
    "time_zone",
    "interval_minutes",
    "active_days",
    "active_from",
    "active_until",
    "event_type",
    "quiet_seconds",
    "filter_tag_id",
    "filter_ticket_kind",
)


@dataclass(frozen=True, slots=True)
class Planned:
    kind: AutomationKind
    columns: dict[str, Any]
    terms: list[datetime]  # the next five (the preview)

    @property
    def next_due_at(self) -> datetime | None:
        return self.terms[0] if self.terms else None


def plan(schedule: Schedule, now: datetime) -> Planned:
    try:
        return _plan(schedule, now)
    except TermError as error:
        raise ValidationFailed(code=error.code) from None


def _plan(schedule: Schedule, now: datetime) -> Planned:
    columns: dict[str, Any] = dict.fromkeys(COLUMNS)
    if isinstance(schedule, OnceIn):
        if schedule.at <= now:
            raise TermError("automation.in_the_past")
        return Planned(AutomationKind.ONCE, columns, [schedule.at])
    if isinstance(schedule, RecurringIn):
        terms = check_recurring(schedule.cron, schedule.time_zone, now)
        columns |= {"cron": schedule.cron, "time_zone": schedule.time_zone}
        return Planned(AutomationKind.RECURRING, columns, terms)
    if isinstance(schedule, HeartbeatIn):
        hours = Hours(
            frozenset(schedule.active_days),
            schedule.active_from,
            schedule.active_until,
            schedule.time_zone,
        )
        check(schedule.interval_minutes, hours)
        columns |= {
            "time_zone": schedule.time_zone,
            "interval_minutes": schedule.interval_minutes,
            "active_days": sorted(hours.days),
            "active_from": schedule.active_from,
            "active_until": schedule.active_until,
        }
        return Planned(
            AutomationKind.HEARTBEAT, columns, _beats(schedule.interval_minutes, hours, now)
        )
    filters = schedule.filter_tag_id is not None or schedule.filter_ticket_kind is not None
    if filters and schedule.event_type != EventType.TICKET_CREATED:
        raise TermError("automation.invalid_filter")
    columns |= {
        "event_type": schedule.event_type,
        "quiet_seconds": schedule.quiet_seconds,
        "filter_tag_id": schedule.filter_tag_id,
        "filter_ticket_kind": schedule.filter_ticket_kind,
    }
    return Planned(AutomationKind.EVENT, columns, [])


def _beats(interval: int, hours: Hours, now: datetime) -> list[datetime]:
    terms: list[datetime] = []
    at = now
    for _ in range(PREVIEW_TERMS):
        at = next_heartbeat(interval, hours, at)
        terms.append(at)
    return terms


def upcoming_of(automation: Automation, now: datetime) -> list[datetime]:
    """The stored automation's next terms from now (none once done, deleted, or for
    an event rule; a `once`: its instant)."""
    if automation.state not in (AutomationState.ACTIVE, AutomationState.PAUSED):
        return []
    if automation.kind == AutomationKind.ONCE:
        return [automation.next_due_at] if automation.next_due_at else []
    if automation.kind == AutomationKind.RECURRING:
        assert automation.cron is not None and automation.time_zone is not None
        return upcoming(automation.cron, automation.time_zone, now, PREVIEW_TERMS)
    if automation.kind == AutomationKind.HEARTBEAT:
        assert automation.interval_minutes is not None
        return _beats(automation.interval_minutes, heartbeats.hours_of(automation), now)
    return []
