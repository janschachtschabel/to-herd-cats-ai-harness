"""The outbox handlers of messaging (spec 4.3). The worker imports this module
(`app/worker/handlers.py`) before it starts; names are stable (stored with each
delivery, metric labels)."""

from app.modules.messaging import notifications, threads
from app.modules.messaging.live_events import LIVE_TYPES, publish_live
from app.modules.wiki.events import PAGE_EVENTS
from app.worker.registry import handler

handler(("message.created", "message.updated"), "notify_on_message")(
    notifications.notify_on_message
)
handler(tuple(LIVE_TYPES), "publish_live")(publish_live)
handler(PAGE_EVENTS, "page_timeline")(threads.page_timeline)
