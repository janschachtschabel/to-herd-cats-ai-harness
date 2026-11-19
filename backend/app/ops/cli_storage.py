"""`python -m app.ops storage copy --to s3|local` and `storage check` (plan M9 task
14): moving attachments between the local directory and S3, and checking the
configured storage (`storage_copy.py`). Output: counts and codes, never keys' content
or secrets; a setting that is missing is named, its value never shown."""

import argparse
from typing import Any

from pydantic import ValidationError

from app.core.clock import Clock
from app.core.config import Settings
from app.core.storage import LocalStorage, Storage, StorageUnavailable, get_storage
from app.ops.storage_copy import CheckFailed, check_storage, copy_files


def add_commands(areas: Any) -> None:
    storage = areas.add_parser("storage", help="move attachments between storages, check one")
    commands = storage.add_subparsers(dest="command", required=True)
    copy = commands.add_parser(
        "copy", help="copy attachments into the other storage (again: only what is missing)"
    )
    copy.add_argument("--to", choices=["s3", "local"], required=True)
    copy.set_defaults(handler=_copy)
    check = commands.add_parser(
        "check", help="write, read and remove a probe in the configured storage"
    )
    check.set_defaults(handler=_check)


def _s3(settings: Settings) -> Storage:
    """The S3 storage of the settings, also while HERD_STORAGE is still local."""
    return get_storage(Settings.model_validate(settings.model_dump() | {"storage": "s3"}))


async def _copy(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    local = LocalStorage(settings.data_dir)
    try:
        s3 = _s3(settings)
    except ValidationError as invalid:
        names = "; ".join(str(e["msg"]).removeprefix("Value error, ") for e in invalid.errors())
        print(f"failed storage.s3_settings: {names}")
        return 1
    source, target = (local, s3) if args.to == "s3" else (s3, local)
    try:
        report = await copy_files(source, target, settings.data_dir / "tmp")
    except StorageUnavailable as failed:
        print(f"failed {failed.reason}")
        return 1
    print(
        f"copied {report.copied}, present {report.present}, gone {report.gone}, "
        f"{report.bytes} bytes"
    )
    return 0


async def _check(args: argparse.Namespace, settings: Settings, clock: Clock) -> int:
    try:
        await check_storage(get_storage(settings))
    except StorageUnavailable as failed:
        print(f"failed {failed.reason}")
        return 1
    except CheckFailed as failed:
        print(f"failed {failed.code}")
        return 1
    print(f"ok {settings.storage}")
    return 0
