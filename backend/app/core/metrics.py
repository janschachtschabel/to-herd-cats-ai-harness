"""Prometheus metrics in an own registry, exposed on the internal port.

With several processes (PROMETHEUS_MULTIPROC_DIR set), every process writes its values
to that directory and /metrics aggregates them with the multiprocess collector.
"""

import os

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client import generate_latest as _generate_latest
from prometheus_client.multiprocess import MultiProcessCollector

UNMATCHED_ROUTE = "<unmatched>"  # one label for every path no route matched

REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "herd_http_requests_total",
    "HTTP requests on the public port.",
    ["method", "route", "status"],
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION = Histogram(
    "herd_http_request_duration_seconds",
    "Duration of HTTP requests on the public port.",
    ["route"],
    registry=REGISTRY,
)


def record_http_request(method: str, route: str | None, status: int, seconds: float) -> None:
    label = route or UNMATCHED_ROUTE
    HTTP_REQUESTS.labels(method=method, route=label, status=str(status)).inc()
    HTTP_REQUEST_DURATION.labels(route=label).observe(seconds)


def render_metrics() -> tuple[bytes, str]:
    """The exposition text and its content type."""
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
        return _generate_latest(registry), CONTENT_TYPE_LATEST
    return _generate_latest(REGISTRY), CONTENT_TYPE_LATEST


COLLAB_SAVES = Counter(
    "herd_collab_saves_total",
    "Saves of live-editing sessions through the internal API, by result.",
    ["result"],
    registry=REGISTRY,
)
COLLAB_CONNECTIONS = Gauge(
    "herd_collab_connections",
    "Open live-editing connections relayed by the public port.",
    registry=REGISTRY,
    multiprocess_mode="livesum",
)
