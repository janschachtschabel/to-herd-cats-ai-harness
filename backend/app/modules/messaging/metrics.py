"""Metrics of live delivery (spec 12.3), in the application's registry
(`app.core.metrics.REGISTRY`, exposed on the internal port)."""

from prometheus_client import Counter, Gauge, Histogram

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
LIVE_QUEUE_DEPTH = Gauge(
    "herd_live_queue_depth",
    "Live events this process received and has not yet handed to its streams.",
    registry=REGISTRY,
    multiprocess_mode="livemax",
)
LIVE_DELIVERY_LAG = Histogram(
    "herd_live_delivery_lag_seconds",
    "Time from a live event's NOTIFY arriving at this process to its streams getting it.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)
LIVE_RESYNCS = Counter(
    "herd_live_resyncs_total",
    "Times this process told its streams to reload instead of delivering events, by "
    "reason: lag (fell behind HERD_LIVE_MAX_LAG_SECONDS), overflow (queue full), "
    "reconnect (LISTEN connection back after a loss), check_failed (database error).",
    ["reason"],
    registry=REGISTRY,
)
