"""Metrics of calendars (spec 12.3), in the application's registry."""

from prometheus_client import Counter

from app.core.metrics import REGISTRY

WINDOW_TOO_DENSE = Counter(
    "herd_calendar_window_too_dense",
    "Event windows refused because they held more occurrences than one call lists "
    "(422 calendar.window_too_dense).",
    registry=REGISTRY,
)
