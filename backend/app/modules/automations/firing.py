"""Firing a due automation (plan M7 decisions 1 to 7, 9, 10, 13): what the due loop
does with one term, in the caller's transaction, so that the term's run (or the note
that it was skipped), its row in the log and the automation's next term commit
together or not at all. Any number of workers may fire at once: the automation's
row is locked while its term fires (`claim_due`) and the log takes a term once.

- A heartbeat's term taken up after its window closed (an outage): no run,
  `skipped_off_hours` (`heartbeats.py`).
- An event rule is due only while counted events wait for its quiet time's end: it
  fires them together (`event_rules.fire_waiting`).
- Otherwise the term fires (`term.fire`: the checks, the run, the log row, the
  system entry).

A `once` is done after its term, whatever the outcome; a recurring automation takes
the first term after "now" (`terms.next_term`), a heartbeat the next in its active
hours (`heartbeat_terms.py`), so after an outage either fires once for all the terms
it missed. A term at which the automation was paused keeps it.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.automations import event_rules, heartbeats, live, terms
from app.modules.automations.models import Automation, AutomationKind, FiringOutcome
from app.modules.automations.repository import AutomationRepository, claim_due
from app.modules.automations.term import Fired, fire

__all__ = ["Fired", "fire_next"]


async def fire_next(session: AsyncSession, now: datetime) -> Fired | None:
    """Fire the most overdue automation due at `now` that no other worker holds;
    None: none is due. The caller commits."""
    while True:
        automation = await claim_due(session, now)
        if automation is None:
            return None
        assert automation.next_due_at is not None  # an active automation has a term
        due_at = automation.next_due_at
        if automation.kind == AutomationKind.EVENT:
            fired = await event_rules.fire_waiting(session, automation, now)
            if fired is None:
                continue  # nothing waited any more: it is due no longer
            return fired
        automations = AutomationRepository(session, automation.org_id)
        if heartbeats.off_hours(automation, due_at, now):
            outcome = FiringOutcome.SKIPPED_OFF_HOURS
            await automations.log(automation, due_at, now, outcome)
            await live.fired(session, automation)
            await automations.advance(automation, _next_due(automation, now))
            return Fired(automation.id, due_at, outcome, None)
        fired = await fire(session, automation, due_at, now)
        if fired.paused is None:
            await automations.advance(automation, _next_due(automation, now))
        return fired


def _next_due(automation: Automation, now: datetime) -> datetime | None:
    if automation.kind == AutomationKind.ONCE:
        return None
    if automation.kind == AutomationKind.HEARTBEAT:
        return heartbeats.next_term(automation, now)
    assert automation.cron is not None and automation.time_zone is not None
    return terms.next_term(automation.cron, automation.time_zone, now)
