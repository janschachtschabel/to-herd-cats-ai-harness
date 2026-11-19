"""Outbox handlers of the calendars (imported by `app/worker/handlers.py`)."""

from app.modules.calendars import live
from app.worker.registry import handler

handler(live.TYPES, "calendar_live")(live.publish)
