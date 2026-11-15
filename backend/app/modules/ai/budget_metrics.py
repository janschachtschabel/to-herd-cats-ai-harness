"""The metric of daily budgets (plan M7 task 11; spec 12.3): agent runs a reached
budget stopped, by the budget's scope (`user`, `agent`, `organisation`), counted by
the worker once the stop has committed (`agents/executor.py`). Terms of automations
a budget skipped are counted as `skipped_budget` firings instead."""

from prometheus_client import Counter

from app.core.metrics import REGISTRY

_stops: Counter | None = None


def budget_stops() -> Counter:
    """Registered on first use (by a worker; an API process exports none)."""
    global _stops  # noqa: PLW0603 -- one registration per process
    if _stops is None:
        _stops = Counter(
            "herd_budget_stops_total",
            "Agent runs this worker stopped at a reached daily budget, by the budget's "
            "scope (user, agent, organisation).",
            ["scope"],
            registry=REGISTRY,
        )
    return _stops
