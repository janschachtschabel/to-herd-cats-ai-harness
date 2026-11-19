"""What the backup administration shows (plan M9 task 13): figures, names and codes,
never an archive's content."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.backups.archives import ArchiveFile
from app.modules.backups.checking import CheckReport, Figures
from app.modules.backups.models import BackupRun, BackupState, BackupTrigger, OffsiteState


class BackupRunOut(BaseModel):
    """One backup. A run with trigger `admin` in state `running` and no archive yet may
    still wait for a worker."""

    id: uuid.UUID
    trigger: BackupTrigger
    state: BackupState
    started_at: datetime
    finished_at: datetime | None
    archive: str | None
    bytes: int | None
    archive_sha256: str | None
    error_code: str | None
    offsite_state: OffsiteState

    @classmethod
    def of(cls, run: BackupRun) -> "BackupRunOut":
        return cls(
            id=run.id,
            trigger=run.trigger,
            state=run.state,
            started_at=run.started_at,
            finished_at=run.finished_at,
            archive=run.archive,
            bytes=run.bytes,
            archive_sha256=run.archive_sha256,
            error_code=run.error_code,
            offsite_state=run.offsite_state,
        )


class ArchiveOut(BaseModel):
    """An archive in the backups directory; `uploaded`: an owner uploaded it."""

    name: str
    bytes: int
    created_at: datetime
    uploaded: bool

    @classmethod
    def of(cls, archive: ArchiveFile) -> "ArchiveOut":
        return cls(
            name=archive.name,
            bytes=archive.size,
            created_at=archive.created_at,
            uploaded=archive.uploaded,
        )


class FiguresOut(BaseModel):
    """`tools_major`: the archive's pg_dump, this installation's pg_restore."""

    app_version: str
    alembic_revision: str
    server_major: int
    tools_major: int | None
    storage: str
    tables: int
    rows: int
    files: int
    file_bytes: int

    @classmethod
    def of(cls, figures: Figures | None) -> "FiguresOut | None":
        if figures is None:
            return None
        return cls(**figures.__dict__)


class ArchiveCheckOut(BaseModel):
    """`problems`: codes, any one blocks replacing (`can_replace` false); `key`:
    whether HERD_SECRET_KEY fits the archive's `enc:` values."""

    archive_name: str
    problems: list[str]
    warnings: list[str]
    created_at: datetime | None
    archive: FiguresOut | None
    installation: FiguresOut | None
    key: Literal["match", "mismatch", "missing", "not_needed"] | None
    can_replace: bool

    @classmethod
    def of(cls, name: str, report: CheckReport) -> "ArchiveCheckOut":
        return cls(
            archive_name=name,
            problems=report.problems,
            warnings=report.warnings,
            created_at=report.created_at,
            archive=FiguresOut.of(report.archive),
            installation=FiguresOut.of(report.installation),
            key=report.key,
            can_replace=not report.problems and report.archive is not None,
        )


class ReplaceIn(BaseModel):
    """The organisation's name, exactly, as the confirmation."""

    confirm: str = Field(min_length=1, max_length=200)


class ReplaceOut(BaseModel):
    archive_name: str


class RestoreAttemptOut(BaseModel):
    """The last attempt to replace the installation from here: `requested` (under way,
    or its process ended), `failed` with a code."""

    state: Literal["requested", "failed"]
    at: datetime
    archive_name: str | None
    code: str | None


class RestoreStatusOut(BaseModel):
    attempt: RestoreAttemptOut | None
