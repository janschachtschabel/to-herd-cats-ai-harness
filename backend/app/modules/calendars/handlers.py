"""Outbox handlers of the calendars (imported by `app/worker/handlers.py`)."""

from app.modules.calendars import live, notifications
from app.modules.calendars.invitation_effects import INVITED, RESPONDED
from app.worker.registry import handler

handler(live.TYPES, "calendar_live")(live.publish)
handler((INVITED,), "calendar_invited")(notifications.on_invited)
handler((RESPONDED,), "calendar_replied")(notifications.on_responded)
