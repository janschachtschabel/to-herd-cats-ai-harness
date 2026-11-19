"""Review M9b, finding F4: a replace that is cancelled while it lets requests drain
(the ten seconds after maintenance began: the API process stops, `ReplaceRunner.stop`,
or Ctrl-C on `restore apply --replace`) leaves maintenance on. Nothing was swapped,
but the installation answers 503 until someone runs `maintenance off` by hand.

`replacing.py`: "When the process stops, the replace is cancelled: before the swap
committed that leaves the old state whole". `replace.py` point 4: "maintenance ends,
`backup.restore_failed` is audited". The drain's sleep is outside the `try` that does
both."""

import asyncio
from pathlib import Path

import pytest

from app.ops.replace import replace_running
from tests.factories_restore import AT, Target, make_archive, source_settings
from tests.real_db import RealDb
from tests.replace_helpers import NAME, marked, running, scalar
from tests.support.clock import SettableClock

ACTIVE = "SELECT count(*) FROM maintenance WHERE active"


async def test_a_replace_cancelled_while_draining_ends_maintenance(
    real_db: RealDb, target: Target, tmp_path: Path, data_dir: Path
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    await running(target, archive)
    replace = asyncio.create_task(
        replace_running(
            target.settings,
            archive,
            confirm=NAME,
            without_secrets=False,
            clock=SettableClock(AT),
            drain_seconds=30,
        )
    )
    async with asyncio.timeout(60):  # the safety archive comes first
        while not await scalar(target.settings, ACTIVE):
            assert not replace.done(), replace.exception()
            await asyncio.sleep(0.1)

    replace.cancel()
    with pytest.raises(asyncio.CancelledError):
        await replace

    assert await marked(target.settings) == 1  # the old state, untouched
    assert not await scalar(target.settings, ACTIVE), "maintenance stayed on"
    assert await scalar(
        target.settings, "SELECT count(*) FROM audit_log WHERE action = 'backup.restore_failed'"
    )
