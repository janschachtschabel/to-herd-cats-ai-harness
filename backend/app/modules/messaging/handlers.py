"""The outbox handlers of messaging (spec 4.3). The worker imports this module
(`app/worker/handlers.py`) before it starts; names are stable (stored with each
delivery, metric labels)."""

from app.modules.messaging import notifications
from app.worker.registry import handler

handler(("message.created", "message.updated"), "notify_on_message")(
    notifications.notify_on_message
)
