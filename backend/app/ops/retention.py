"""Which backup archives stay (plan M9 decision 7): grandfather-father-son.

Counted over good archives only, newest first: the newest of each of the last `daily`
days that have one, then, older than those, the newest of each of `weekly` ISO weeks
not yet represented, then, older still, the newest of each of `monthly` months not yet
represented; and always the newest good archive. Days, weeks and months are UTC. A
failed archive never counts (and `create_backup` has removed it already).

`keep_set` is pure; `apply_retention` reads the directory and removes the archives
(with their sidecars) outside the set. It runs only after a new good archive, so a
run of failures never thins out what is there. restic gets the same counts
(`restic forget --keep-daily/--keep-weekly/--keep-monthly`, its own reading of them:
the periods overlap, so offsite reaches back less far than the volume).
"""

import os
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.ops.archive import read_sidecar, sidecar_of
from app.ops.backup import ARCHIVE_PREFIX
from app.ops.manifest import ManifestInvalid


@dataclass(frozen=True)
class KeepRule:
    daily: int
    weekly: int
    monthly: int


@dataclass(frozen=True)
class ArchiveInfo:
    name: str
    created_at: datetime
    ok: bool


def keep_set(archives: Sequence[ArchiveInfo], rule: KeepRule) -> set[str]:
    good = sorted((a for a in archives if a.ok), key=lambda a: a.created_at, reverse=True)
    if not good:
        return set()
    kept = [good[0]]
    tiers: list[tuple[int, Callable[[datetime], Hashable]]] = [
        (rule.daily, lambda at: at.astimezone(UTC).date()),
        (rule.weekly, lambda at: at.astimezone(UTC).isocalendar()[:2]),
        (rule.monthly, lambda at: (at.astimezone(UTC).year, at.astimezone(UTC).month)),
    ]
    start = 0  # the tiers go back in time one after the other
    for count, period in tiers:
        represented = {period(a.created_at) for a in kept} if start else set()
        taken = 0
        for index in range(start, len(good)):
            if taken == count:
                break
            key = period(good[index].created_at)
            if key in represented:
                continue
            represented.add(key)
            if good[index] not in kept:
                kept.append(good[index])
            taken += 1
            start = index + 1
    return {a.name for a in kept}


def list_archives(directory: Path) -> list[ArchiveInfo]:
    """The archives in `directory`: good when the sidecar reads (a backup that failed
    leaves none), with the creation time from the manifest."""
    found = []
    for path in sorted(directory.glob(f"{ARCHIVE_PREFIX}*.tar")):
        try:
            manifest, _ = read_sidecar(path)
            at = datetime.strptime(manifest.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            found.append(ArchiveInfo(path.name, at, ok=True))
        except (ManifestInvalid, OSError, ValueError):
            found.append(ArchiveInfo(path.name, _mtime(path), ok=False))
    return found


def apply_retention(directory: Path, rule: KeepRule) -> list[str]:
    """Remove the good archives outside `keep_set`; the names removed. Archives that
    are not good (no readable sidecar: copied in by hand) are left alone."""
    archives = list_archives(directory)
    keep = keep_set(archives, rule)
    removed = []
    for archive in archives:
        if archive.ok and archive.name not in keep:
            path = directory / archive.name
            path.unlink(missing_ok=True)
            sidecar_of(path).unlink(missing_ok=True)
            removed.append(archive.name)
    return removed


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(os.stat(path).st_mtime, tz=UTC)
