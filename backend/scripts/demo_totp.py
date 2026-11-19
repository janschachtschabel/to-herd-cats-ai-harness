"""The second factor in the demo (M9b Task 16), through the public API, only with
`--totp-file PATH`: Ben sets up TOTP in his profile as the browser does (setup with his
password, confirmed with the first code), and the key and his ten recovery codes go into
PATH, a new file readable by its owner alone (0600). Nothing of it is printed. Put the
key into an authenticator app (or compute the codes from it) to sign in as Ben with
password and code.

The codes are computed here as an authenticator app does (RFC 6238: SHA-1, six digits,
30-second steps), with nothing from the app's own code.
"""

import base64
import hashlib
import hmac
import os
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from scripts.demo_api import DemoFailed, call

TOTP = "/api/auth/me/totp"
STEP_SECONDS = 30
DIGITS = 6


@dataclass
class SeededTotp:
    enabled_for: str | None = None  # the person's key in the demo ("ben"), none: no TOTP


def code_at(secret: str, unix_time: float) -> str:
    """The code of `secret` (base32, padding optional) at `unix_time`."""
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    counter = struct.pack(">Q", int(unix_time // STEP_SECONDS))
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def reserve(path: Path) -> int:
    """A new file only its owner may read, open for writing; an existing file is never
    overwritten (taken before TOTP is on, so its key always has a place to go)."""
    try:
        return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exists:
        raise DemoFailed(f"{path} exists already; not overwritten") from exists


async def build(
    person: httpx.AsyncClient,
    *,
    key: str,
    email: str,
    password: str,
    totp_file: Path | None,
    now: Callable[[], float] = time.time,
) -> SeededTotp:
    """With `totp_file`: TOTP for the signed-in `person` (the demo's `key`, `email`).
    Confirming ends the person's other sessions, so run it after everything else she
    does in the demo."""
    if totp_file is None:
        return SeededTotp()
    fd = reserve(totp_file)
    try:
        setup = await call(person, "POST", f"{TOTP}/setup", {"password": password})
        secret = str(setup["secret"])
        code = code_at(secret, now())
        confirmed = await call(person, "POST", f"{TOTP}/confirm", {"code": code})
    except BaseException:
        os.close(fd)
        os.unlink(totp_file)
        raise
    lines = [
        f"# TOTP of {email} in the demo: the key for an authenticator app and the",
        "# recovery codes (each works once). Keep this file to yourself.",
        f"key: {secret}",
        f"uri: {setup['uri']}",
        "recovery codes:",
        *confirmed["recovery_codes"],
    ]
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
    return SeededTotp(enabled_for=key)
