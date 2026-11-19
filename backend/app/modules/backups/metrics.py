"""Gauges of backups (plan M9 decision 11), read by every worker from `backup_run` on a
timer: a backup job is short-lived and cannot be scraped, the table can. Registered
by the first worker of a process (`backup_metrics()`), never on import, so an API pod
exports none. Timestamps in seconds since the epoch, 0 while there is none.

- `herd_backup_last_success_timestamp_seconds`, `..._last_failure_...`: the last
  finish of a good and of a failed backup;
- `herd_backup_last_bytes`: the size of the last good archive;
- `herd_backup_offsite_last_success_timestamp_seconds`, `..._last_failure_...`: the
  last good backup whose restic push worked, and failed;
- `herd_backup_alert_after_seconds`: HERD_BACKUP_ALERT_AFTER_HOURS, the age of the last
  good backup at which HerdBackupTooOld fires (so the rule file stays fixed).
"""

from dataclasses import dataclass
from datetime import datetime

from prometheus_client import Gauge

from app.core.config import Settings
from app.core.db import Database
from app.core.metrics import REGISTRY
from app.modules.backups.repository import BackupRunRepository


@dataclass(frozen=True, slots=True)
class BackupMetrics:
    last_success: Gauge
    last_failure: Gauge
    last_bytes: Gauge
    offsite_success: Gauge
    offsite_failure: Gauge
    alert_after: Gauge


_metrics: BackupMetrics | None = None


def _gauge(name: str, text: str) -> Gauge:
    return Gauge(name, text, registry=REGISTRY, multiprocess_mode="livemax")


def backup_metrics() -> BackupMetrics:
    global _metrics  # noqa: PLW0603 -- one registration per process
    if _metrics is None:
        _metrics = BackupMetrics(
            last_success=_gauge(
                "herd_backup_last_success_timestamp_seconds",
                "When the last good backup finished (backup_run; 0: none yet).",
            ),
            last_failure=_gauge(
                "herd_backup_last_failure_timestamp_seconds",
                "When the last failed backup finished (backup_run; 0: none).",
            ),
            last_bytes=_gauge("herd_backup_last_bytes", "Size of the last good archive."),
            offsite_success=_gauge(
                "herd_backup_offsite_last_success_timestamp_seconds",
                "When the last good backup that reached the restic repository finished.",
            ),
            offsite_failure=_gauge(
                "herd_backup_offsite_last_failure_timestamp_seconds",
                "When the last good backup whose restic push failed finished.",
            ),
            alert_after=_gauge(
                "herd_backup_alert_after_seconds",
                "Age of the last good backup at which HerdBackupTooOld fires "
                "(HERD_BACKUP_ALERT_AFTER_HOURS).",
            ),
        )
    return _metrics


async def update_backup_metrics(database: Database, settings: Settings) -> None:
    async with database.session_factory() as session:
        figures = await BackupRunRepository(session).figures()
    metrics = backup_metrics()
    metrics.last_success.set(_seconds(figures.last_ok))
    metrics.last_failure.set(_seconds(figures.last_failed))
    metrics.last_bytes.set(figures.last_bytes or 0)
    metrics.offsite_success.set(_seconds(figures.offsite_ok))
    metrics.offsite_failure.set(_seconds(figures.offsite_failed))
    metrics.alert_after.set(settings.backup_alert_after_hours * 3600)


def _seconds(at: datetime | None) -> float:
    return at.timestamp() if at is not None else 0.0
