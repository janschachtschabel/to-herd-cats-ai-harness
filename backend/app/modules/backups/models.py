"""The backups' state (plan M9 decision 11): one `backup_run` row per backup, written
by whoever makes it (the command line, the scheduled job, the administration). A
short-lived job cannot be asked how it went; this table can (the worker's gauges, the
administration's list). Figures and codes only: the archive's file name, its size and
SHA-256, never content.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk

MAX_ARCHIVE_CHARS = 120
MAX_ERROR_CHARS = 64


class BackupTrigger(StrEnum):
    SCHEDULE = "schedule"
    CLI = "cli"
    ADMIN = "admin"
    PRE_RESTORE = "pre_restore"


class BackupState(StrEnum):
    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"
    INTERRUPTED = "interrupted"  # its process ended without finishing (restore marks it)


class OffsiteState(StrEnum):
    OFF = "off"  # no offsite repository configured, or the backup itself failed
    OK = "ok"
    FAILED = "failed"


def _one_of(column: str, values: type[StrEnum]) -> CheckConstraint:
    return CheckConstraint(f"{column} IN ({', '.join(repr(v.value) for v in values)})", column)


class BackupRun(UuidPk, OrgScoped, Base):
    __tablename__ = "backup_run"
    __table_args__ = (
        _one_of("trigger", BackupTrigger),
        _one_of("state", BackupState),
        _one_of("offsite_state", OffsiteState),
        Index("ix_backup_run_started_at", "started_at", "id"),
    )

    trigger: Mapped[BackupTrigger] = mapped_column(String(16), nullable=False)
    state: Mapped[BackupState] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archive: Mapped[str | None] = mapped_column(String(MAX_ARCHIVE_CHARS))  # file name only
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    archive_sha256: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(MAX_ERROR_CHARS))
    offsite_state: Mapped[OffsiteState] = mapped_column(
        String(16), nullable=False, default=OffsiteState.OFF, server_default=OffsiteState.OFF.value
    )
