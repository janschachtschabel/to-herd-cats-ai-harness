"""Review M9b final, finding F2-2: after one "Einspielen" (replace), no later backup
of that installation can be restored any more.

The swap drops and creates schema `public` (`swap.py`). The new schema belongs to the
connecting role instead of `pg_database_owner`, and for such a schema `pg_dump` writes
an entry `SCHEMA - public <owner>` into every dump from then on. The allow-list of
the F1 fix (`dump_toc.py`) knows no such entry and refuses the archive as
`archive.dump_foreign`: in `restore check`, "Prüfen", a restore into an empty
installation and the next replace alike. The installation's own nightly backups are
then worthless without anyone being told."""

from datetime import timedelta
from pathlib import Path

from app.modules.backups.models import BackupTrigger
from app.ops.backup import create_backup
from app.ops.replace import replace_running
from app.ops.restore_checks import check_restore
from tests.factories_restore import AT, Target, make_archive, source_settings
from tests.real_db import RealDb
from tests.replace_helpers import NAME, running
from tests.support.clock import SettableClock


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
    # and it can be put back.
    await replace_running(
        target.settings,
        outcome.archive,
        confirm=NAME,
        without_secrets=False,
        clock=SettableClock(AT + timedelta(days=2)),
        drain_seconds=0,
    )
