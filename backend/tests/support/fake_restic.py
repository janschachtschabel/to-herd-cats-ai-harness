#!/usr/bin/env python3
"""A stand-in for `restic` in tests (plan M9 task 3): never touches a repository or
the network. Installed as `restic` on a directory put first on PATH
(`install_fake_restic`); every call appends its arguments and its whole environment to
`restic.log` next to it. `restic.fail` (subcommands, one per line) makes those fail
with exit 1; `cat config` answers 10 (no repository) until `init` ran."""

import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def install_fake_restic(directory: Path, *, fail: tuple[str, ...] = ()) -> Path:
    """`directory/restic` (this file), and its failures; the directory."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "restic"
    shutil.copyfile(__file__, target)
    target.chmod(0o755)
    if fail:
        (directory / "restic.fail").write_text("\n".join(fail))
    return directory


def calls(directory: Path) -> list[dict]:  # type: ignore[type-arg]
    log = directory / "restic.log"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]


def main() -> int:
    args = sys.argv[1:]
    with (HERE / "restic.log").open("a") as log:
        log.write(json.dumps({"argv": args, "env": dict(os.environ)}) + "\n")
    command = args[0] if args else ""
    failing = HERE / "restic.fail"
    if failing.exists() and command in failing.read_text().split():
        return 1
    if command == "cat" and not (HERE / "repository").exists():
        return 10
    if command == "init":
        (HERE / "repository").touch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
