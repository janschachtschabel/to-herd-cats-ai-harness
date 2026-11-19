"""Offsite retention with a real restic (module review M9a, N1).

restic groups snapshots by `host,paths` before it applies a keep rule unless told
otherwise, and every backup sends an archive under a new name: each snapshot would be
a group of its own and `--keep-last=1` would keep all of them. `push_offsite` groups
by `host,tags` (every snapshot carries the host and tag `herd`), so the rule of the
volume thins the repository out as well.

Needs restic on PATH; skipped without it, unless HERD_TEST_RESTIC_REQUIRED is set (CI
installs the image's restic and sets it, so the test cannot pass by skipping there).
"""

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.backups.models import OffsiteState
from app.ops.archive import sidecar_of
from app.ops.offsite import push_offsite, restic_env
from app.ops.retention import KeepRule
from tests.support.clock import SettableClock

PASSWORD = "offsite-restic-password-0123456789"
DAY = datetime(2026, 11, 10, 2, 30, tzinfo=UTC)


def _restic() -> str:
    found = shutil.which("restic")
    if found is None:
        if os.environ.get("HERD_TEST_RESTIC_REQUIRED"):
            pytest.fail("restic is required (HERD_TEST_RESTIC_REQUIRED) but not on PATH")
        pytest.skip("no restic on PATH")
    return found


async def test_offsite_retention_keeps_only_what_the_rule_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    restic = _restic()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    settings = Settings(
        backup_offsite_repository=str(tmp_path / "repo"),
        backup_offsite_password=SecretStr(PASSWORD),
    )
    rule = KeepRule(daily=1, weekly=0, monthly=0)
    backups = tmp_path / "backups"
    backups.mkdir()
    for day in range(3):
        at = DAY + timedelta(days=day)
        archive = backups / f"herd-{at:%Y%m%dT%H%M%SZ}-1.0.0.tar"
        archive.write_bytes(os.urandom(1024))
        sidecar_of(archive).write_text("{}")
        assert await push_offsite(settings, archive, rule, SettableClock(at)) == OffsiteState.OK
    listed = subprocess.run(  # noqa: S603, ASYNC221
        [restic, "snapshots", "--json"],
        env=restic_env(settings, os.environ),
        capture_output=True,
        check=True,
    )
    snapshots = json.loads(listed.stdout)
    # keep-last=1 and keep-daily=1: only the newest snapshot stays.
    assert len(snapshots) == 1, f"{len(snapshots)} snapshots kept offsite"
    assert any(p.endswith("herd-20261112T023000Z-1.0.0.tar") for p in snapshots[0]["paths"])
