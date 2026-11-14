"""Event rules at work (plan M7 decisions 8 and 9): what an event does to the active
rules of its kind in its space (`on_event`, from the outbox handler, in the delivery's
transaction), and what the due loop does at a quiet time's end (`fire_waiting`).

For each rule (its row locked, in a fixed order):

1. An event its own run caused on an object that run was about starts nothing (a
   rule never reacts to its own effect on the same object).
2. Its filters (`ticket.created`: a tag, a kind) are read on the ticket as it is now.
3. An event about an object the rule's run could not read at its place is not taken
   in (`event_sight.py`): nothing of it reaches the place or the log.
4. The event is taken in once (`automation_event`, keyed by rule and event): an event
   handed over again does nothing more.
5. Depth: an event a run caused gives a run one step further down that run's chain
   (`chain_depth` + 1, counting handovers and events together); past
   `MAX_CHAIN_DEPTH` the term is logged `skipped_depth` and starts nothing.
6. Quiet time: within `quiet_seconds` of the rule's last term the event waits; the
   rule's `next_due_at` becomes the quiet time's end, when the due loop fires every
   waiting event as one term. Otherwise the term fires now, with the events still
   waiting (a due loop running late). The term's checks are those of any term
   (`term.fire`); a run is told the kind, the objects' ids and the count
   (`runs.assignment`). A new quiet time starts with every term.

Times come from the caller ("now"): the handler's clock, the due loop's.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.outbox import Event
from app.modules.agents.models import MAX_CHAIN_DEPTH
from app.modules.automations import event_sight
from app.modules.automations.event_repository import Cause, EventRuleRepository
from app.modules.automations.models import Automation, EventType, FiringOutcome
from app.modules.automations.repository import AutomationRepository
from app.modules.automations.term import Fired, fire

EVENT_TYPES = frozenset(EventType)
# Ids of a payload that are no object a run is told of.
NOT_OBJECTS = frozenset({"conversation_id", "run_id"})


async def on_event(session: AsyncSession, event: Event, now: datetime) -> list[str]:
    """What the event did to the rules: the outcome of each term it fired now (for
    the metric; a run started, a skip, a pause)."""
    if event.type not in EVENT_TYPES or event.space_id is None:
        return []
    repo = EventRuleRepository(session, event.org_id)
    rules = await repo.rules_for(event.type, event.space_id)
    if not rules:
        return []
    cause = await repo.cause(event.run_id) if event.run_id is not None else None
    depth = cause.depth + 1 if cause is not None else 0
    fired = [await _take(session, repo, rule, event, cause, depth, now) for rule in rules]
    return [label for label in fired if label is not None]


async def _take(
    session: AsyncSession,
    repo: EventRuleRepository,
    rule: Automation,
    event: Event,
    cause: Cause | None,
    depth: int,
    now: datetime,
) -> str | None:
    """The outcome of the term the event fired now; None: it fired none."""
    if cause is not None and cause.automation_id == rule.id and event.subject_id in cause.subjects:
        return None
    if not await _matches(repo, rule, event) or not await event_sight.may_tell(
        session, rule, event
    ):
        return None
    if not await repo.take(rule, event.id, event.subject_id, _ids(event), depth):
        return None
    if depth > MAX_CHAIN_DEPTH:
        due_at = await repo.free_term(rule.id, now)
        firing_id = uuid7()
        automations = AutomationRepository(session, rule.org_id)
        outcome = FiringOutcome.SKIPPED_DEPTH
        await automations.log(rule, due_at, now, outcome, firing_id=firing_id)
        await repo.assign(rule.id, firing_id, only=event.id)
        return outcome.value
    if rule.quiet_until is not None and now < rule.quiet_until:
        if rule.next_due_at is None:
            rule.next_due_at = rule.quiet_until
            await session.flush()
        return None
    fired = await _fire(session, repo, rule, await repo.free_term(rule.id, now), now)
    return fired.label


async def fire_waiting(session: AsyncSession, rule: Automation, now: datetime) -> Fired | None:
    """The waiting events of a rule whose quiet time ended, as one term (the rule is
    locked by the due loop); None: none waited."""
    repo = EventRuleRepository(session, rule.org_id)
    assert rule.next_due_at is not None
    if not await repo.waiting(rule.id):
        rule.next_due_at = None
        await session.flush()
        return None
    return await _fire(session, repo, rule, await repo.free_term(rule.id, rule.next_due_at), now)


async def _fire(
    session: AsyncSession,
    repo: EventRuleRepository,
    rule: Automation,
    due_at: datetime,
    now: datetime,
) -> Fired:
    waiting = await repo.waiting(rule.id)
    depth = max(e.depth for e in waiting)
    fired = await fire(session, rule, due_at, now, chain_depth=depth)
    if fired.firing_id is None:  # paused: the events wait for it to run again
        rule.next_due_at = due_at
    else:
        await repo.assign(rule.id, fired.firing_id)
        rule.next_due_at = None
        assert rule.quiet_seconds is not None
        rule.quiet_until = now + timedelta(seconds=rule.quiet_seconds)
    await session.flush()
    return fired


async def _matches(repo: EventRuleRepository, rule: Automation, event: Event) -> bool:
    if rule.event_type != EventType.TICKET_CREATED:
        return True
    if rule.filter_ticket_kind is not None:
        if await repo.ticket_kind(event.subject_id) != rule.filter_ticket_kind:
            return False
    if rule.filter_tag_id is not None:
        return await repo.tagged(event.subject_id, rule.filter_tag_id)
    return True


def _ids(event: Event) -> dict[str, Any]:
    """The ids of the event's payload a run may be told (never anything else)."""
    return {
        key: value
        for key, value in event.payload.items()
        if key.endswith("_id") and key not in NOT_OBJECTS and isinstance(value, str)
    }
