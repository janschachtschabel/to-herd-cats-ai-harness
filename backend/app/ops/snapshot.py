"""One consistent view of the database for a backup (plan M9 decision 4): a
`REPEATABLE READ` read-only transaction exports its snapshot (`pg_export_snapshot()`),
`pg_dump --snapshot` dumps exactly that, and the figures of the manifest are read in
the same transaction: rows per table, the attachment files to copy, the Alembic
revision, how many `enc:` values each secret column holds and the names of the `env:`
references. This module is the snapshot's repository: its SQL lives here.

Secret columns are found, not listed: every text column of the models whose name ends
in `_ref` (`secret_ref`, `client_secret_ref`, ...), so a new one is counted without a
change here.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import String, Text, func, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.models_registry import Base
from app.modules.wiki.models import Attachment
from app.ops.pgtools import server_major


class NoSchema(Exception):  # noqa: N818 (a state of the database)
    """The database has no migrated schema to back up."""


@dataclass(frozen=True)
class SnapshotFile:
    key: str
    size: int
    sha256: str


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    server_major: int
    alembic_revision: str
    tables: dict[str, int]
    files: list[SnapshotFile]
    enc_values: dict[str, int]
    env_refs: list[str]


@asynccontextmanager
async def open_snapshot(engine: AsyncEngine) -> AsyncIterator[Snapshot]:
    """The snapshot and its figures; it stays exported while the block runs."""
    async with engine.connect() as raw:
        conn = await raw.execution_options(
            isolation_level="REPEATABLE READ", postgresql_readonly=True
        )
        async with conn.begin():
            snapshot_id = str(await conn.scalar(text("SELECT pg_export_snapshot()")))
            revision = await _revision(conn)
            enc_values, env_refs = await secret_figures(conn)
            yield Snapshot(
                snapshot_id=snapshot_id,
                server_major=await server_major(conn),
                alembic_revision=revision,
                tables=await row_counts(conn),
                files=await attachment_files(conn),
                enc_values=enc_values,
                env_refs=env_refs,
            )


async def _revision(conn: AsyncConnection) -> str:
    if await conn.scalar(text("SELECT to_regclass('alembic_version')")) is None:
        raise NoSchema()
    heads = sorted((await conn.scalars(text("SELECT version_num FROM alembic_version"))).all())
    if not heads:
        raise NoSchema()
    return ",".join(heads)


async def row_counts(conn: AsyncConnection) -> dict[str, int]:
    """Rows of every table in the current schema (catalog names, quoted)."""
    names = (
        await conn.scalars(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
                " ORDER BY tablename"
            )
        )
    ).all()
    counts = {}
    for name in names:
        quoted = '"' + name.replace('"', '""') + '"'
        counts[name] = int(await conn.scalar(text(f"SELECT count(*) FROM {quoted}")) or 0)  # noqa: S608
    return counts


async def attachment_files(conn: AsyncConnection) -> list[SnapshotFile]:
    """One entry per stored file (content-addressed: rows of one content share it)."""
    rows = await conn.execute(
        select(Attachment.storage_key, func.min(Attachment.size), func.min(Attachment.sha256))
        .group_by(Attachment.storage_key)
        .order_by(Attachment.storage_key)
    )
    return [SnapshotFile(key=k, size=int(n), sha256=s) for k, n, s in rows.all()]


def secret_columns() -> list[tuple[str, str]]:
    """(table, column) of every text column named `*_ref` in the models."""
    found = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if column.name.endswith("_ref") and isinstance(column.type, Text | String):
                found.append((table.name, column.name))
    return sorted(found)


async def secret_figures(conn: AsyncConnection) -> tuple[dict[str, int], list[str]]:
    """`enc:` values per "table.column" and the sorted names of `env:` references."""
    enc_values: dict[str, int] = {}
    env_names: set[str] = set()
    rows = await conn.execute(
        text(
            "SELECT table_name, column_name FROM information_schema.columns"
            " WHERE table_schema = current_schema()"
        )
    )
    present = {(str(t), str(c)) for t, c in rows.all()}
    for table, column in secret_columns():
        if (table, column) not in present:  # a database at an older revision
            continue
        model = Base.metadata.tables[table]
        col = model.c[column]
        count = await conn.scalar(
            select(func.count()).select_from(model).where(col.startswith("enc:"))
        )
        enc_values[f"{table}.{column}"] = int(count or 0)
        names = await conn.scalars(
            select(func.substr(col, 5)).where(col.startswith("env:")).distinct()
        )
        env_names.update(str(n) for n in names.all())
    return enc_values, sorted(env_names)
