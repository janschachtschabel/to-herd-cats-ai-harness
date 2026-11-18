"""The administration's replace runner (review M9b F3): the claim is taken and looked
at in one step, spans the request's check, and is given back when the request ends
without a replace; `stop` cancels every replace it started."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.core.clock import SYSTEM_CLOCK
from app.core.config import get_settings
from app.modules.backups.replacing import ReplaceBusy, ReplaceRunner


async def test_a_claim_holds_the_runner_until_released_or_started() -> None:
    cancelled: list[Path] = []

    async def slow(settings: Any, archive: Path, **kwargs: Any) -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(archive)
            raise

    runner = ReplaceRunner(slow)
    claim = runner.claim()
    assert runner.busy
    with pytest.raises(ReplaceBusy) as busy:
        runner.claim()
    assert busy.value.code == "backup.busy"
    claim.release()
    claim.release()  # once is enough; the second does nothing
    assert not runner.busy

    runner.claim().start(get_settings(), Path("a.tar"), "Org", SYSTEM_CLOCK)
    await asyncio.sleep(0)
    assert runner.busy
    with pytest.raises(ReplaceBusy) as running:
        runner.claim()
    assert running.value.code == "backup.restore_running"

    await runner.stop()
    assert cancelled == [Path("a.tar")]
    assert not runner.busy
