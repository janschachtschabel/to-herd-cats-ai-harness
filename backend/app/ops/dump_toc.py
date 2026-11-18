"""What of an archive's dump a restore runs (review M9b F1): only what this code's own
schema is made of.

`pg_dump -Fc` keeps every object's definition as text in the dump's table of contents,
and `pg_restore` writes that text out unchanged, so a dump is a script chosen by
whoever made the archive. Before a restore (and in every check) the table of contents
is listed (`pg_restore --list`, from the dump's first bytes: it stops reading after the
table) and each entry judged:

- restored: tables, their data, sequences, defaults, indexes and constraints in
  schema `public`; functions and triggers only by the names our migrations give them
  (FUNCTIONS, TRIGGERS; `tests/test_dump_toc.py` holds them to the migrated schema);
- left out: grants (`ACL`, `DEFAULT ACL`; a restore never sets privileges) and a
  comment on schema `public` (the swap's own marker, `swap.py`);
- anything else (another schema, an extension, a comment, a view, a rule, an event
  trigger, a function of another name ...) refuses the archive: `archive.dump_foreign`.

The restore then gets exactly the entries judged restorable (`--use-list`), from an
in-memory file (no scratch file on disk). An entry's text is still the archive's: an
uploaded archive is trusted like the operator's shell (docs/SICHERUNG.md); the other
layers are psql's `\\restrict` (`pgtools.restrict_capable`) and the swap's check that
its transaction is still its own.
"""

import asyncio
import os
import re
import shutil
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass

from app.ops.pgtools import ToolFailed

FOREIGN = "archive.dump_foreign"
# A dump's table of contents is a few hundred KiB; more than this is no dump of ours.
TOC_MAX_BYTES = 64 * 1024 * 1024
FUNCTIONS = frozenset(
    {
        "herd_conversation_kind_fixed",
        "herd_message_one_level_threads",
        "herd_message_system_only_in_threads",
        "herd_space_default_ticket_statuses",
        "herd_work_item_hierarchy",
        "herd_work_item_same_space",
        "herd_work_item_status_changed_at",
    }
)
TRIGGERS = frozenset(
    {
        "conversation_kind_fixed",
        "message_one_level_threads",
        "message_system_only_in_threads",
        "space_default_ticket_statuses",
        "work_item_hierarchy",
        "work_item_same_space",
        "work_item_status_changed_at",
    }
)
_IN_PUBLIC = (
    "TABLE DATA",
    "FK CONSTRAINT",
    "SEQUENCE OWNED BY",
    "SEQUENCE SET",
    "SEQUENCE",
    "TABLE",
    "DEFAULT",
    "INDEX",
    "CONSTRAINT",
)
_LEFT_OUT = ("DEFAULT ACL ", "ACL ", "COMMENT - SCHEMA public ")
_ENTRY = re.compile(r"(\d+); \d+ \d+ (.+)")
_FUNCTION = re.compile(r"FUNCTION public (\w+)\(\) ")
_TRIGGER = re.compile(r"TRIGGER public \w+ (\w+) ")


@dataclass(frozen=True)
class Listing:
    """The entries to restore, as a `--use-list` file, and the dump again as a whole
    stream (the bytes the listing read, then the rest)."""

    use_list: str
    dump: AsyncIterator[bytes]


def judge(toc: str) -> str:
    """The `--use-list` file of the restorable entries of `pg_restore --list` output;
    ToolFailed(FOREIGN) if any entry is not ours."""
    kept: list[str] = []
    for line in toc.splitlines():
        if not line.strip() or line.startswith(";"):
            continue
        entry = _ENTRY.fullmatch(line)
        if entry is None:
            raise ToolFailed(FOREIGN)
        what = entry.group(2)
        if what.startswith(_LEFT_OUT):
            continue
        if not _ours(what):
            raise ToolFailed(FOREIGN)
        kept.append(line)
    return "\n".join(kept) + "\n"


def _ours(what: str) -> bool:
    if any(what.startswith(f"{kind} public ") for kind in _IN_PUBLIC):
        return True
    function = _FUNCTION.match(what)
    if function is not None:
        return function.group(1) in FUNCTIONS
    trigger = _TRIGGER.match(what)
    return trigger is not None and trigger.group(1) in TRIGGERS


async def list_dump(dump: AsyncIterator[bytes]) -> Listing:
    """List and judge the dump read from `dump` (ToolFailed: `restore.tool_missing`,
    FOREIGN, or `restore.pg_restore_failed` when it is no dump pg_restore can read)."""
    pg_restore = shutil.which("pg_restore")
    if pg_restore is None:
        raise ToolFailed("restore.tool_missing")
    process = await asyncio.create_subprocess_exec(
        pg_restore,
        "--list",
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C.UTF-8"},
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    read: list[bytes] = []
    try:
        toc = await _listed(process, dump, read)
    except BaseException:
        with suppress(ProcessLookupError):
            process.kill()
        await process.wait()
        raise
    return Listing(judge(toc), _again(read, dump))


async def _listed(
    process: asyncio.subprocess.Process, dump: AsyncIterator[bytes], read: list[bytes]
) -> str:
    stdin, stdout = process.stdin, process.stdout
    assert stdin is not None and stdout is not None  # PIPEs
    feeding = asyncio.create_task(_feed(dump, stdin, read))
    try:
        toc = await stdout.read()
        status = await process.wait()
    except BaseException:
        feeding.cancel()
        with suppress(asyncio.CancelledError):
            await feeding
        raise
    # Never cancelled once pg_restore ended: a cancel inside the dump's iterator would
    # end it, and the restore needs the rest. Its next write finds the pipe closed.
    await feeding
    if status != 0:
        raise ToolFailed("restore.pg_restore_failed", status)
    return toc.decode("utf-8", "replace")


async def _feed(dump: AsyncIterator[bytes], into: asyncio.StreamWriter, read: list[bytes]) -> None:
    size = 0
    try:
        async for chunk in dump:
            read.append(chunk)
            size += len(chunk)
            if size > TOC_MAX_BYTES:
                into.close()  # pg_restore sees the end: no dump of ours
                return
            into.write(chunk)
            await into.drain()
        into.close()
    except (BrokenPipeError, ConnectionResetError):
        pass  # pg_restore has read its table of contents


async def _again(read: list[bytes], rest: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    while read:
        yield read.pop(0)
    async for chunk in rest:
        yield chunk
