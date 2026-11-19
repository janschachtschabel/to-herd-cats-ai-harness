"""Review M9b final, finding F2-2: after one "Einspielen" (replace), no later backup
of that installation could be restored any more.

The swap drops and creates schema `public` (`swap.py`). The new schema belongs to the
connecting role instead of `pg_database_owner`, and for such a schema `pg_dump` writes
an entry `SCHEMA - public <owner>` into every dump from then on. The allow-list of
the F1 fix (`dump_toc.py`) knew no such entry and refused the archive as
`archive.dump_foreign`: in `restore check`, "Prüfen", a restore into an empty
installation and the next replace alike.

Ruling: the allow-list takes `SCHEMA public` and its comment whatever their owner
(and plpgsql as the only extension); a backup made after a replace can be checked,
restored into an empty installation and used for the next replace, whose safety
archive is valid too."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import asyncpg
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.core.config import Settings, get_settings
from app.core.listen import asyncpg_dsn
from app.modules.backups.models import BackupTrigger
from app.ops.backup import create_backup
from app.ops.replace import replace_running
from app.ops.restore import restore_into_empty
from app.ops.restore_checks import check_restore
from tests.factories_restore import AT, KEY, Target, make_archive, source_settings
from tests.real_db import RealDb
from tests.replace_helpers import MARK, NAME, running, scalar
from tests.support.clock import SettableClock


@asynccontextmanager
async def _empty_installation(tmp_path: Path) -> AsyncIterator[Settings]:
    admin = make_url(get_settings().test_database_url)
    name = f"herd_m9b_f22_{uuid.uuid4().hex[:10]}"
    connection = await asyncpg.connect(asyncpg_dsn(admin))
    try:
        await connection.execute(f'CREATE DATABASE "{name}"')
        yield Settings(
            database_url=admin.set(database=name).render_as_string(hide_password=False),
            data_dir=tmp_path / "empty-data",
            backup_dir=tmp_path / "empty-backups",
            secret_key=SecretStr(KEY),
        )
    finally:
        await connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await connection.close()


async def test_a_backup_made_after_a_replace_can_be_restored(
    real_db: RealDb, target: Target, tmp_path: Path, data_dir: Path
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)
    await replace_running(
        target.settings,
        archive,
        confirm=NAME,
        without_secrets=False,
        clock=SettableClock(AT),
        drain_seconds=0,
    )

    # The replaced installation's next backup (the nightly one, say) ...
    later = SettableClock(AT + timedelta(days=1))
    outcome = await create_backup(target.settings, trigger=BackupTrigger.SCHEDULE, clock=later)
    assert outcome.archive is not None, outcome.error_code

    # ... is an archive of this software: the check must not call it foreign,
    check = await check_restore(target.settings, outcome.archive)
    assert "archive.dump_foreign" not in check.problems
    # it can be restored into an empty installation,
    async with _empty_installation(tmp_path) as empty:
        await restore_into_empty(
            empty, outcome.archive, without_secrets=False, clock=SettableClock(AT)
        )
        assert await scalar(empty, "SELECT count(*) FROM organization WHERE name = 'Real Org'")
    # and used for the next replace,
    second = await replace_running(
        target.settings,
        outcome.archive,
        confirm=NAME,
        without_secrets=False,
        clock=SettableClock(AT + timedelta(days=2)),
        drain_seconds=0,
    )
    assert not await scalar(
        target.settings, f"SELECT count(*) FROM user_group WHERE name = '{MARK}'"
    )
    # whose safety archive is valid too.
    safety = await check_restore(target.settings, second.safety_archive)
    assert "archive.dump_foreign" not in safety.problems
