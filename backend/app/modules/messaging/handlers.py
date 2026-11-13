"""The outbox handlers of messaging (spec 4.3). The worker imports this module
(`app/worker/handlers.py`) before it starts; names are stable (stored with each
delivery, metric labels)."""

from app.modules.messaging import notifications
from app.modules.messaging.live_events import LIVE_TYPES, publish_live
from app.worker.registry import handler

handler(("message.created", "message.updated"), "notify_on_message")(
    notifications.notify_on_message
)
handler(tuple(LIVE_TYPES), "publish_live")(publish_live)
