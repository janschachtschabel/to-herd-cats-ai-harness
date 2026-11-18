"""The check ("Prüfen") in the administration (plan M9 task 13): an archive's
manifest against this installation, as figures and codes only, never content.

The archive is read back first, in a thread (`verify_archive`, several GiB take a
while); then the checks a replace makes (`ops/restore_checks.check_on` with
`into_empty` false: a running installation is no problem here). Shown side by side:
app version, Alembic revision, PostgreSQL major version (the archive's server against
this one), `pg_dump` against this `pg_restore`, the storage, tables, rows and files;
whether HERD_SECRET_KEY fits (`match`, `mismatch`, `missing`, or `not_needed` when the
archive holds no `enc:` value); the problems (any one blocks "Einspielen") and the
warnings.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.config import Settings
from app.ops.archive import verify_archive
from app.ops.manifest import Manifest
from app.ops.pgtools import ToolFailed, client_major, server_major
from app.ops.restore import heads
from app.ops.restore_checks import check_on
from app.ops.snapshot import attachment_files, row_counts
from app.version import app_version

KEY_STATES = {
    "restore.secret_key_mismatch": "mismatch",
    "restore.secret_key_missing": "missing",
}


@dataclass(frozen=True)
class Figures:
    app_version: str
    alembic_revision: str
    server_major: int
    tools_major: int | None  # the archive's pg_dump, this installation's pg_restore
    storage: str
    tables: int
    rows: int
    files: int
    file_bytes: int


@dataclass
class CheckReport:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    archive: Figures | None = None
    installation: Figures | None = None
    key: str | None = None  # match | mismatch | missing | not_needed


async def check_archive(session: AsyncSession, settings: Settings, path: Path) -> CheckReport:
    """Read back without a database connection; then the checks on the session's."""
    problems = await asyncio.to_thread(verify_archive, path)
    if problems:
        return CheckReport(problems=problems)
    conn = await session.connection()
    check = await check_on(conn, settings, path, into_empty=False, verified=True)
    report = CheckReport(problems=check.problems, warnings=check.warnings)
    if check.manifest is None:
        return report
    report.created_at = check.manifest.created()
    report.archive = _of_manifest(check.manifest)
    report.installation = await _installation(conn, settings)
    report.key = _key(check.manifest, check.problems)
    return report


def _of_manifest(manifest: Manifest) -> Figures:
    return Figures(
        app_version=manifest.app_version,
        alembic_revision=manifest.alembic_revision,
        server_major=manifest.server_major,
        tools_major=manifest.tools_major(),
        storage=manifest.storage,
        tables=len(manifest.tables),
        rows=sum(manifest.tables.values()),
        files=manifest.files.get("count", 0),
        file_bytes=manifest.files.get("bytes", 0),
    )


async def _installation(conn: AsyncConnection, settings: Settings) -> Figures:
    tables = await row_counts(conn)
    files = await attachment_files(conn)
    try:
        tools: int | None = client_major("pg_restore")
    except ToolFailed:
        tools = None
    return Figures(
        app_version=app_version(),
        alembic_revision=",".join(sorted(await heads(conn))),
        server_major=await server_major(conn),
        tools_major=tools,
        storage=settings.storage,
        tables=len(tables),
        rows=sum(tables.values()),
        files=len(files),
        file_bytes=sum(f.size for f in files),
    )


def _key(manifest: Manifest, problems: list[str]) -> str:
    if not any(manifest.enc_values.values()):
        return "not_needed"
    for problem, state in KEY_STATES.items():
        if problem in problems:
            return state
    return "match"
