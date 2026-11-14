"""The outbox handler of automations (plan M7 task 5): every event an event rule may
listen to goes to the active rules of its kind in its space (`event_rules.on_event`),
in the delivery's transaction; idempotent (a rule takes an event in once), never
committing itself. Imported by `app/worker/handlers.py`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import SYSTEM_CLOCK
from app.core.outbox import Event
from app.modules.automations.event_rules import on_event
from app.modules.automations.models import EventType
from app.worker.registry import handler


@handler([kind.value for kind in EventType], "automation_events")
async def automation_events(session: AsyncSession, event: Event) -> None:
    await on_event(session, event, SYSTEM_CLOCK.now())
