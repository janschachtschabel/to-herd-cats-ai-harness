"""Settings of operations (plan M9): backups. `Settings` inherits them, so
`get_settings()` stays the one source."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from cronsim import CronSim, CronSimError
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings

_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


class OpsSettings(BaseSettings):
    # Where backup archives go (`python -m app.ops backup create`): a volume of its
    # own, mode 0700; the archives are not encrypted (docs: protect the volume).
    backup_dir: Path = Path("/backups")
    # When `python -m app.ops backup schedule` (the compose service) makes a backup:
    # cron, five fields, UTC. The chart's CronJob has its own schedule value.
    backup_schedule: str = "30 2 * * *"
    # Grandfather-father-son: the newest archive of each of the last days, of the
    # weeks before and of the months before stays (`ops/retention.py`).
    backup_keep_daily: int = Field(default=7, ge=0, le=1000)
    backup_keep_weekly: int = Field(default=4, ge=0, le=1000)
    backup_keep_monthly: int = Field(default=6, ge=0, le=1000)
    # Offsite with restic (`ops/offsite.py`): the repository (empty: off) and its
    # password. The storage's own credentials (AWS_*, B2_*, ...) go to restic only.
    backup_offsite_repository: str = ""
    backup_offsite_password: SecretStr | None = None
    # The worker exports it as herd_backup_alert_after_seconds: HerdBackupTooOld fires
    # when the last good backup is older.
    backup_alert_after_hours: float = Field(default=26.0, gt=0, le=24 * 60)

    @model_validator(mode="after")
    def _backup_settings_fit(self) -> Self:
        try:
            CronSim(self.backup_schedule, _EPOCH)
        except CronSimError:
            raise ValueError(
                "HERD_BACKUP_SCHEDULE must be a cron expression with five fields"
            ) from None
        password = self.backup_offsite_password
        if password is not None and not password.get_secret_value():
            self.backup_offsite_password = None  # compose: `${...:-}`
        if self.backup_offsite_repository and self.backup_offsite_password is None:
            raise ValueError("HERD_BACKUP_OFFSITE_REPOSITORY needs HERD_BACKUP_OFFSITE_PASSWORD")
        return self
