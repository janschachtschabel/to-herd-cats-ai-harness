"""The outbox handlers of automations, imported by `app/worker/handlers.py`; each in
the delivery's transaction, never committing itself.

- `automation_events` (plan M7 task 5): every event an event rule may listen to goes
  to the active rules of its kind in its space (`event_rules.on_event`); idempotent
  (a rule takes an event in once).
- `automation_live` (task 7): a change of an automation becomes one
  `automation.changed` per person who may see it (`live.py`)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import SYSTEM_CLOCK
from app.core.outbox import Event
from app.modules.automations.event_rules import on_event
from app.modules.automations.live import CHANGED, automation_live
from app.modules.automations.models import EventType
from app.worker.registry import handler


@handler([kind.value for kind in EventType], "automation_events")
async def automation_events(session: AsyncSession, event: Event) -> None:
    await on_event(session, event, SYSTEM_CLOCK.now())


handler([CHANGED], "automation_live")(automation_live)
