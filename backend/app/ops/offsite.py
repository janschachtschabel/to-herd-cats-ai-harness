"""Offsite copies with restic (plan M9 decision 8, spec 12.6).

On when HERD_BACKUP_OFFSITE_REPOSITORY is set. After a good backup: `restic cat
config` (`init` when there is no repository yet, exit status 10), `restic backup` of
the archive and its sidecar (host and tag `herd`), `restic forget --prune` with the rule
of the volume over all of them (`--group-by host,tags`: grouped by paths, every archive's
new name would be a group of its own and keep-last would keep it), and
on the first day of a month (UTC) `restic check --read-data-subset=5%`. restic
encrypts on the client; the archives on the volume are not encrypted.

restic's environment is built here, never inherited: PATH, HOME, the repository and
its password from the settings, and of the process's environment only the storage's
own variables (`AWS_*`, `B2_*`, `AZURE_*`, `GOOGLE_*`, `OS_*`, `ST_*`, `RESTIC_*` other
than the repository and the password), which come from the backup's own Secret or
`backup.env`. Nothing else of the app (database password, secret key, AI keys) reaches
it; the password is never an argument. Its output is not logged: a failure is the step
and the exit status.
"""

import asyncio
import logging
import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from app.core.clock import Clock
from app.core.config import Settings
from app.modules.backups.models import OffsiteState
from app.ops.archive import sidecar_of
from app.ops.retention import KeepRule

logger = logging.getLogger(__name__)

PASSTHROUGH_PREFIXES = ("AWS_", "B2_", "AZURE_", "GOOGLE_", "OS_", "ST_", "RESTIC_")
# Set from the settings, or never from outside: where the repository is and its secret.
OWN_RESTIC = frozenset(
    {
        "RESTIC_REPOSITORY",
        "RESTIC_REPOSITORY_FILE",
        "RESTIC_PASSWORD",
        "RESTIC_PASSWORD_FILE",
        "RESTIC_PASSWORD_COMMAND",
    }
)
NO_REPOSITORY = 10  # restic's exit status when the repository does not exist
TAG = "herd"


def restic_env(settings: Settings, passthrough: Mapping[str, str]) -> dict[str, str]:
    password = settings.backup_offsite_password
    env = {
        "PATH": passthrough.get("PATH", "/usr/bin:/bin"),
        "HOME": passthrough.get("HOME", "/tmp"),  # noqa: S108 (restic's cache, tmpfs)
        "RESTIC_REPOSITORY": settings.backup_offsite_repository,
        "RESTIC_PASSWORD": password.get_secret_value() if password is not None else "",
    }
    for name, value in passthrough.items():
        if name.startswith(PASSTHROUGH_PREFIXES) and name not in OWN_RESTIC:
            env[name] = value
    return env


async def push_offsite(
    settings: Settings, archive: Path, rule: KeepRule, clock: Clock
) -> OffsiteState:
    if not settings.backup_offsite_repository:
        return OffsiteState.OFF
    env = restic_env(settings, os.environ)
    status = await _restic(env, "cat", "config")
    if status == NO_REPOSITORY:
        status = await _restic(env, "init")
    steps: list[tuple[str, ...]] = [
        ("backup", "--tag", TAG, "--host", TAG, str(archive), str(sidecar_of(archive))),
        (
            "forget",
            "--tag",
            TAG,
            # restic groups by host and paths by default; every archive has a new name,
            # so each snapshot would be a group of its own and nothing would ever go.
            "--group-by",
            "host,tags",
            "--prune",
            "--keep-last=1",
            f"--keep-daily={rule.daily}",
            f"--keep-weekly={rule.weekly}",
            f"--keep-monthly={rule.monthly}",
        ),
    ]
    if clock.now().day == 1:
        steps.append(("check", "--read-data-subset=5%"))
    if status != 0:
        return _failed("repository", status)
    for step in steps:
        status = await _restic(env, *step)
        if status != 0:
            return _failed(step[0], status)
    return OffsiteState.OK


def _failed(step: str, status: int) -> OffsiteState:
    logger.warning("backup.offsite_failed", extra={"step": step, "status": status})
    return OffsiteState.FAILED


async def _restic(env: dict[str, str], *args: str) -> int:
    path = shutil.which("restic", path=env["PATH"])
    if path is None:
        return 127
    process = await asyncio.create_subprocess_exec(
        path,
        *args,
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return await process.wait()
