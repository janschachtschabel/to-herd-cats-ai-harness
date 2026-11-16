"""Whether an archive may be restored here (plan M9 decisions 2, 5 and 6), as codes.

Problems (any one refuses the restore): the archive's own (`verify_archive`),
`restore.archive_newer` (a revision this code does not know), `restore.target_not_empty`
(a table in schema `public`), `restore.file_conflict` (a key of the archive is stored
here with other content; local or S3, `HERD_STORAGE`), `restore.storage_unavailable`
(the object store did not answer), `restore.server_too_old` (the server's major version is
below the archive's), `restore.tools_too_old` (`pg_restore` is older than the archive's
`pg_dump`), `restore.secret_key_mismatch` and `restore.secret_key_missing` (the archive
has `enc:` values and neither HERD_SECRET_KEY nor HERD_SECRET_KEY_PREVIOUS has its key
id; `--without-secrets` restores anyway). Warnings: `restore.env_missing:<NAME>` (an
`env:` reference whose variable is not set) and, with a key problem,
`restore.secrets_unreadable:<table.column>=<n>`.
"""

import os
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import Settings
from app.core.db import make_engine
from app.core.migrations import known_revisions
from app.core.secrets import key_id
from app.core.storage import StorageKeyError, StorageUnavailable, get_storage, stored_sha256
from app.ops.archive import FILES_PREFIX, MANIFEST_MEMBER, PREFIX, verify_archive
from app.ops.manifest import Manifest
from app.ops.pgtools import ToolFailed, client_major, server_major

KEY_PROBLEMS = frozenset({"restore.secret_key_mismatch", "restore.secret_key_missing"})


@dataclass
class RestoreCheck:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest: Manifest | None = None


async def check_restore(settings: Settings, archive: Path) -> RestoreCheck:
    """The check on a connection of its own (`restore check`)."""
    engine = make_engine(settings.database())
    try:
        async with engine.connect() as conn:
            return await check_on(conn, settings, archive)
    finally:
        await engine.dispose()


async def check_on(
    conn: AsyncConnection, settings: Settings, archive: Path, *, into_empty: bool = True
) -> RestoreCheck:
    """With `into_empty` false (replacing a running installation, `replace.py`) a
    database with tables is no problem."""
    problems = verify_archive(archive)
    if problems:
        return RestoreCheck(problems=problems)
    manifest = inner_manifest(archive)
    check = RestoreCheck(manifest=manifest)
    heads = set(manifest.alembic_revision.split(","))
    if not heads <= known_revisions()[1]:
        check.problems.append("restore.archive_newer")
    tables = await conn.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"))
    if tables and into_empty:
        check.problems.append("restore.target_not_empty")
    try:
        if await _file_conflict(settings, manifest):
            check.problems.append("restore.file_conflict")
    except StorageKeyError:  # a member name no storage key can have
        check.problems.append("archive.format_unknown")
    except StorageUnavailable:
        check.problems.append("restore.storage_unavailable")
    if await server_major(conn) < manifest.server_major:
        check.problems.append("restore.server_too_old")
    try:
        if client_major("pg_restore") < int(manifest.pg_dump_version.split(".")[0]):
            check.problems.append("restore.tools_too_old")
    except ToolFailed:
        check.problems.append("restore.tools_too_old")
    _check_keys(check, settings, manifest)
    check.warnings[:0] = [
        f"restore.env_missing:{name}" for name in manifest.env_refs if not os.environ.get(name)
    ]
    return check


def inner_manifest(archive: Path) -> Manifest:
    with tarfile.open(archive, "r:") as tar:
        handle = tar.extractfile(PREFIX + MANIFEST_MEMBER)
        assert handle is not None  # verify_archive found it
        return Manifest.from_json(handle.read())


def _check_keys(check: RestoreCheck, settings: Settings, manifest: Manifest) -> None:
    unreadable = {column: n for column, n in sorted(manifest.enc_values.items()) if n}
    if not unreadable:
        return
    ours = {
        key_id(k.get_secret_value())
        for k in (settings.secret_key, settings.secret_key_previous)
        if k is not None
    }
    if not ours:
        check.problems.append("restore.secret_key_missing")
    elif manifest.key_id not in ours:
        check.problems.append("restore.secret_key_mismatch")
    else:
        return
    check.warnings += [f"restore.secrets_unreadable:{c}={n}" for c, n in unreadable.items()]


async def _file_conflict(settings: Settings, manifest: Manifest) -> bool:
    storage = get_storage(settings)
    for name, member in manifest.members.items():
        if not name.startswith(FILES_PREFIX):
            continue
        stored = await stored_sha256(storage, name.removeprefix(FILES_PREFIX))
        if stored is not None and stored != member["sha256"]:
            return True
    return False
