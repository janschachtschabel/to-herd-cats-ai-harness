"""Where temporary files of uploads, imports and exports go: `HERD_DATA_DIR/tmp`, on
the data volume, never `TMPDIR` (a tmpfs in compose, so RAM).

The files are unnamed where the system allows it (`O_TMPFILE`) or unlinked right after
creation, so a crash leaves nothing behind in the usual case; whatever is left anyway
(a system without either, a file put there by hand) is removed at start once it is
older than `SPOOL_MAX_AGE_SECONDS`. The age keeps a file of another replica's request
in progress safe, since replicas share the volume.
"""

import logging
import os
import stat
import tempfile
import time
from pathlib import Path
from typing import IO

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SPOOL_MAX_AGE_SECONDS = 24 * 60 * 60


def spool_dir(data_dir: Path | None = None) -> Path:
    return (data_dir or get_settings().data_dir) / "tmp"


def spooled_file(max_size: int) -> IO[bytes]:
    """Kept in memory up to `max_size` bytes, then a file under `spool_dir()`."""
    directory = spool_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return tempfile.SpooledTemporaryFile(max_size=max_size, dir=str(directory))  # noqa: SIM115


def remove_stale_spools(data_dir: Path, *, now: float | None = None) -> int:
    """Remove entries of `data_dir/tmp` older than the safe age (links are removed,
    never followed; directories are left alone). The number removed."""
    directory = spool_dir(data_dir)
    limit = (time.time() if now is None else now) - SPOOL_MAX_AGE_SECONDS
    removed = 0
    try:
        entries = list(os.scandir(directory))
    except FileNotFoundError:
        return 0
    for entry in entries:
        try:
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode) or info.st_mtime >= limit:
                continue
            os.unlink(entry.path)
            removed += 1
        except FileNotFoundError:
            continue
    if removed:
        logger.info("stale spool files removed", extra={"count": removed})
    return removed
