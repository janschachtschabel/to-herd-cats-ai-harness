"""Metrics of automations and the page review (plan M7 task 11; spec 12.3), in the
application's registry. Labels are outcomes and reasons, never ids or content.

They are registered by the first due loop of a process (`automation_metrics()`), not
on import: a process without a worker (role `api`) must not export a backlog of 0
that hides one no worker works off. The gauges are read from the database on a timer
(`DueLoop.update_metrics`), so every worker reports the same values (take the max)
and they stay current while a pass hangs. Counters count after the commit: a term
fired in the due loop (`DueLoop.fire_one`) or by the event handler
(`count_firing`, run by the lane once its batch committed).
"""

from dataclasses import dataclass

from prometheus_client import Counter, Gauge
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import after_commit
from app.core.metrics import REGISTRY


@dataclass(frozen=True, slots=True)
class AutomationMetrics:
    firings: Counter
    set_aside: Counter
    due: Gauge
    oldest_due: Gauge
    paused: Gauge
    review_reminders: Counter
    review_spaces: Gauge


_metrics: AutomationMetrics | None = None


def automation_metrics() -> AutomationMetrics:
    """The metrics, registered on first use."""
    global _metrics  # noqa: PLW0603 -- one registration per process
    if _metrics is None:
        _metrics = AutomationMetrics(
            firings=Counter(
                "herd_automation_firings_total",
                "Terms of automations fired by this worker (due loop and event rules), by "
                "outcome: started, skipped_* or paused_<reason>.",
                ["outcome"],
                registry=REGISTRY,
            ),
            set_aside=Counter(
                "herd_automation_terms_set_aside_total",
                "Terms the due loop of this worker could not fire (their transaction "
                "failed) and set aside for a backoff.",
                registry=REGISTRY,
            ),
            due=Gauge(
                "herd_automations_due",
                "Active automations whose term has come and that no worker fired yet "
                "(from the database).",
                registry=REGISTRY,
                multiprocess_mode="livemax",
            ),
            oldest_due=Gauge(
                "herd_automations_oldest_due_seconds",
                "How long the oldest due term has waited to be fired (0 without one; from "
                "the database).",
                registry=REGISTRY,
                multiprocess_mode="livemax",
            ),
            paused=Gauge(
                "herd_automations_paused",
                "Automations paused, by reason: manual, owner (the owner may no longer run "
                "it), failing (three failed runs in a row) (from the database).",
                ["reason"],
                registry=REGISTRY,
                multiprocess_mode="livemax",
            ),
            review_reminders=Counter(
                "herd_wiki_review_reminders_total",
                "Pages whose review came due and that the daily pass reminded "
                "(page.review_due emitted) in this worker.",
                registry=REGISTRY,
            ),
            review_spaces=Gauge(
                "herd_wiki_review_spaces_unchecked",
                "Spaces with a review interval whose pages the daily pass has not been "
                "through today (UTC; from the database).",
                registry=REGISTRY,
                multiprocess_mode="livemax",
            ),
        )
    return _metrics


def count_firing(session: AsyncSession, label: str) -> None:
    """Count a term fired in a handler once the handler's delivery has committed."""

    async def count(_: AsyncSession) -> None:
        automation_metrics().firings.labels(outcome=label).inc()

    after_commit(session, count)
