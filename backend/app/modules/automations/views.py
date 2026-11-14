"""Automations and their log as the API shows them (`schemas.py`), from the service's
views."""

from app.modules.automations.models import AutomationFiring
from app.modules.automations.schemas import (
    AutomationOut,
    FiringOut,
    LastRunOut,
    NamedOut,
    PlaceOut,
)
from app.modules.automations.service import AutomationView
from app.modules.messaging.models import ConversationKind

PLACE_TYPES = {
    ConversationKind.DM: "dm",
    ConversationKind.CHANNEL: "channel",
    ConversationKind.THREAD_TICKET: "ticket",
}


def automation_out(view: AutomationView) -> AutomationOut:
    row, automation = view.row, view.row.automation
    last = None
    if row.last is not None:
        last = LastRunOut(
            firing_id=row.last.id,
            due_at=row.last.due_at,
            fired_at=row.last.fired_at,
            outcome=row.last.outcome,
            heartbeat_ok=row.last.heartbeat_ok,
            run_id=row.last.run_id,
            run_state=row.run.state if row.run else None,
            stop_reason=row.run.stop_reason if row.run else None,
        )
    channel = row.place.kind == ConversationKind.CHANNEL
    return AutomationOut(
        id=automation.id,
        kind=automation.kind,
        state=automation.state,
        paused_reason=automation.paused_reason,
        version=automation.version,
        instruction=automation.instruction,
        agent=NamedOut(id=automation.agent_id, name=row.agent_name),
        owner=NamedOut(id=automation.owner_user_id, name=row.owner_name),
        place=PlaceOut(
            type=PLACE_TYPES[ConversationKind(row.place.kind)],
            conversation_id=row.place.id,
            space_id=row.place.space_id,
            name=row.place.name if channel else None,
            ticket_number=row.ticket_number,
        ),
        next_due_at=automation.next_due_at,
        cron=automation.cron,
        time_zone=automation.time_zone,
        interval_minutes=automation.interval_minutes,
        active_days=automation.active_days,
        active_from=automation.active_from,
        active_until=automation.active_until,
        event_type=automation.event_type,
        quiet_seconds=automation.quiet_seconds,
        filter_tag_id=automation.filter_tag_id,
        filter_ticket_kind=automation.filter_ticket_kind,
        last_run=last,
        upcoming=view.upcoming,
        may_edit=view.may_edit,
        may_control=view.may_control,
    )


def firing_out(firing: AutomationFiring) -> FiringOut:
    return FiringOut(
        id=firing.id,
        due_at=firing.due_at,
        fired_at=firing.fired_at,
        outcome=firing.outcome,
        run_id=firing.run_id,
        heartbeat_ok=firing.heartbeat_ok,
    )
