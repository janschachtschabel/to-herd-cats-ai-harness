"""The worker's gauges (spec 12.3; review M3 N3, N4).

They are created by the first worker of a process (`worker_metrics()`), not on
import: a process without a worker (role `api`) must not export an outbox backlog of
0 that hides one no worker works off. Every worker reads the backlog from the
database on a timer of its own, so all of them report the same values (take the max)
and they stay current while a pass hangs.
"""

from dataclasses import dataclass

from prometheus_client import Gauge

from app.core.metrics import REGISTRY


@dataclass(frozen=True, slots=True)
class WorkerMetrics:
    pending: Gauge
    oldest_pending: Gauge
    failed: Gauge
    last_pass: Gauge


_metrics: WorkerMetrics | None = None


def worker_metrics() -> WorkerMetrics:
    """The gauges, registered on first use."""
    global _metrics  # noqa: PLW0603 -- one registration per process
    if _metrics is None:
        _metrics = WorkerMetrics(
            pending=Gauge(
                "herd_outbox_pending",
                "Outbox events neither dispatched nor failed (from the database).",
                registry=REGISTRY,
                multiprocess_mode="livemax",
            ),
            oldest_pending=Gauge(
                "herd_outbox_oldest_pending_seconds",
                "Age of the oldest pending outbox event (0 without one; from the database).",
                registry=REGISTRY,
                multiprocess_mode="livemax",
            ),
            failed=Gauge(
                "herd_outbox_failed",
                "Outbox events that gave up on a handler after their last attempt and are "
                "still in the table (from the database, so it survives restarts).",
                registry=REGISTRY,
                multiprocess_mode="livemax",
            ),
            last_pass=Gauge(
                "herd_worker_last_pass_timestamp_seconds",
                "Unix time this worker last finished a batch or found nothing due.",
                registry=REGISTRY,
                multiprocess_mode="liveall",
            ),
        )
    return _metrics
