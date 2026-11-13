"""Metrics of live delivery (spec 12.3), in the application's registry
(`app.core.metrics.REGISTRY`, exposed on the internal port)."""

from prometheus_client import Counter, Gauge

from app.core.metrics import REGISTRY

SSE_CONNECTIONS = Gauge(
    "herd_sse_connections",
    "Open live-delivery streams (GET /api/stream) of this process.",
    registry=REGISTRY,
    multiprocess_mode="livesum",
)
LIVE_EVENTS = Counter(
    "herd_live_events_total",
    "Live events this process received over LISTEN herd_live, by SSE event name.",
    ["type"],
    registry=REGISTRY,
)
