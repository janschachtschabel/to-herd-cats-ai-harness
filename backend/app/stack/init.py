"""`python -m app.stack init`: the first service of the Hostinger stack (plan M9 task 19,
docs/HOSTINGER.md). Every other service waits until it has ended with exit 0.

- Generates the secrets once, 256 random bits each as hex, into two volumes: the
  database password alone into `--db-secret` (the database container sees nothing
  else), the key for stored secrets (`HERD_SECRET_KEY_FILE`) and the internal token
  (`HERD_INTERNAL_TOKEN_FILE`) into `--secrets`. An existing secret is never replaced;
  an empty one is a broken volume (exit 1), since a new database password would lock
  the app out of its own database.
- Checks DOMAIN: a bare host name (the Traefik labels take it unchanged, and
  `Host(`https://…`)` only gives Traefik's 404). Anything else stops the start with a
  clear message (exit 2) instead of a silent correction.
- The one-time admin (ADMIN_EMAIL, ADMIN_PASSWORD): checked with the app's own rules
  (length, breached list, context words), so that the app never refuses it at its
  start; the password goes into `--secrets` for HERD_BOOTSTRAP_ADMIN_PASSWORD_FILE,
  and that file is emptied once the password is cleared in `.env`.
- Missing values (no DOMAIN, no admin password) are skipped with a note: exit 0.

Output names variables and files, never a secret.
"""

import re
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.core.password_check import context_words, refuse_guessable
from app.core.password_rule import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

DB_PASSWORD = "db_password"  # noqa: S105 (a file name)
GENERATED = ("secret_key", "internal_token")
PASSWORD_FILE = "bootstrap_admin_password"  # noqa: S105 (a file name)
INVALID = 2
BROKEN = 1

_LABEL = r"(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
_HOST = re.compile(rf"{_LABEL}(\.{_LABEL})*")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_EXAMPLE = "wiki.example.org"


class Refused(Exception):
    """A value in `.env` the stack cannot use; the message says which and why."""


async def run_init(
    env: Mapping[str, str], *, secrets_dir: Path, db_secret_dir: Path, out: TextIO
) -> int:
    def say(line: str) -> None:
        print(f"init: {line}", file=out, flush=True)

    try:
        domain = _domain(env.get("DOMAIN", ""))
        password = await _admin(env.get("ADMIN_EMAIL", ""), env.get("ADMIN_PASSWORD", ""))
    except Refused as refused:
        say(str(refused))
        return INVALID
    try:
        created = _ensure_secret(db_secret_dir / DB_PASSWORD)
        created += sum(_ensure_secret(secrets_dir / name) for name in GENERATED)
    except Refused as refused:
        say(str(refused))
        return BROKEN
    _write(secrets_dir / PASSWORD_FILE, password)
    say(f"secrets ready ({created} created, {3 - created} kept)")
    if domain:
        say(f"DOMAIN {domain}: Traefik serves https://{domain}")
    else:
        say("DOMAIN is empty: skipped, the app is not reachable from outside yet")
    if password:
        say("one-time admin ready: created at the app's start if nobody exists yet")
    else:
        say("ADMIN_PASSWORD is empty: no one-time admin (skipped)")
    return 0


def _domain(value: str) -> str:
    if not value or (len(value) <= 253 and _HOST.fullmatch(value)):
        return value
    shown = value if len(value) <= 80 else value[:80] + "…"
    raise Refused(
        f"DOMAIN must be a bare host name like {_EXAMPLE}, without https://, path or "
        f"port; got {shown!r}. / DOMAIN muss der reine Hostname sein, z. B. {_EXAMPLE} "
        "(ohne https://, ohne Pfad, ohne Port). Fix it in .env and deploy again."
    )


async def _admin(email: str, password: str) -> str:
    """The admin password the app may use ("" for none), checked like the app does."""
    if not password:
        return ""
    if not email:
        raise Refused("ADMIN_PASSWORD is set but ADMIN_EMAIL is empty: set both or neither")
    if not _EMAIL.fullmatch(email):
        raise Refused("ADMIN_EMAIL must be an e-mail address like chef@example.org")
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise Refused(
            f"ADMIN_PASSWORD must be {PASSWORD_MIN_LENGTH} to {PASSWORD_MAX_LENGTH} "
            "characters long / muss 10 bis 200 Zeichen lang sein"
        )
    org_name = Settings.model_fields["bootstrap_org_name"].default
    name = email.split("@")[0]
    try:
        await refuse_guessable(password, context_words(org_name=org_name, email=email, name=name))
    except ValidationFailed as refused:
        raise Refused(
            f"ADMIN_PASSWORD is easy to guess ({refused.code}): it is on a list of leaked "
            "passwords or holds a word of the address or product; choose another one / "
            "ist leicht zu erraten, bitte ein anderes wählen"
        ) from None
    return password


def _ensure_secret(path: Path) -> int:
    """1 when `path` was created, 0 when it was there; Refused when it is empty."""
    if path.exists():
        if not path.read_text(encoding="utf-8").strip():
            raise Refused(
                f"{path} is empty: the volume is broken. Restore the file from a copy, "
                "or remove the stack's volumes to start afresh (all data is lost)"
            )
        return 0
    _write(path, secrets.token_hex(32))
    return 1


def _write(path: Path, content: str) -> None:
    """Write `path` (mode 0400) in one step: a crash leaves the old file or the new one."""
    temporary = path.with_name(f".{path.name}.new")
    temporary.unlink(missing_ok=True)
    temporary.touch(mode=0o600)
    temporary.write_text(content, encoding="utf-8")
    temporary.chmod(0o400)
    temporary.replace(path)
