"""What is particular to a heartbeat (plan M7 decision 7), beside its terms
(`heartbeat_terms.py`):

- its terms come only inside its active hours; a term the due loop takes up after its
  window closed (an outage, longer than `LATE_GRACE`) is skipped
  (`skipped_off_hours`), and the next term is the next opening;
- an answer of exactly `HEARTBEAT_OK` (after trimming) is delivered nowhere: the run
  ends `completed`, and its term's row notes it (`automation_firing.heartbeat_ok`).
  The instructions tell the model the rule (`runtime/context.py`).
"""

from datetime import datetime

from app.modules.automations.heartbeat_terms import Hours, inside, next_heartbeat
from app.modules.automations.models import Automation, AutomationKind
from app.modules.automations.terms import MIN_SPACING
from app.runtime.context import HEARTBEAT_OK

LATE_GRACE = MIN_SPACING  # a term taken up this late still runs, wherever the window is


def hours_of(automation: Automation) -> Hours:
    assert automation.kind == AutomationKind.HEARTBEAT
    assert automation.active_days is not None and automation.time_zone is not None
    assert automation.active_from is not None and automation.active_until is not None
    return Hours(
        frozenset(automation.active_days),
        automation.active_from,
        automation.active_until,
        automation.time_zone,
    )


def next_term(automation: Automation, now: datetime) -> datetime:
    assert automation.interval_minutes is not None
    return next_heartbeat(automation.interval_minutes, hours_of(automation), now)


def off_hours(automation: Automation, due_at: datetime, now: datetime) -> bool:
    """A heartbeat's term taken up after its window closed (not just a little late)."""
    if automation.kind != AutomationKind.HEARTBEAT or now - due_at < LATE_GRACE:
        return False
    return not inside(hours_of(automation), now)


def is_ok(answer: str | None) -> bool:
    return answer is not None and answer.strip() == HEARTBEAT_OK
