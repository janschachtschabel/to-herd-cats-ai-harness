"""`python -m app.stack set-secret-key`: puts a saved HERD_SECRET_KEY into the Hostinger
stack's secrets volume (docs/HOSTINGER.md, "Wiederherstellen"). init generates a key on
the first deploy and never replaces one, so on a new server the saved key of the old one
gets in only this way; without it the stored AI keys and client secrets of a restored
archive stay unreadable.

Reads the key from standard input (one line), checks it like the app does (at least 32
characters) and that it is one word (no spaces or control characters: a paste error),
and writes it in one step with mode 0400; in the stack it runs as the image's user
10001, which then owns the file. Output names the key ids (as the backup manifest
does), never a key. Exit 0 written or unchanged, 2 refused, 1 the volume is unusable.
"""

from pathlib import Path
from typing import TextIO

from app.core.config import SECRET_KEY_MIN_LENGTH
from app.core.secrets import key_id
from app.stack.init import BROKEN, INVALID, unusable, write_secret

KEY_FILE = "secret_key"


def run_set_secret_key(text: str, *, secrets_dir: Path, out: TextIO) -> int:
    def say(line: str) -> None:
        print(f"set-secret-key: {line}", file=out, flush=True)

    key = text.rstrip("\r\n")
    if len(key) < SECRET_KEY_MIN_LENGTH or not key.isprintable() or any(c.isspace() for c in key):
        say(
            f"HERD_SECRET_KEY must be one line of at least {SECRET_KEY_MIN_LENGTH} "
            "characters without spaces; nothing written. / Der Schlüssel muss eine Zeile "
            f"mit mindestens {SECRET_KEY_MIN_LENGTH} Zeichen ohne Leerzeichen sein."
        )
        return INVALID
    path = secrets_dir / KEY_FILE
    try:
        old = path.read_text(encoding="utf-8").rstrip("\r\n") if path.exists() else None
        if old == key:
            say(f"HERD_SECRET_KEY unchanged (key id {key_id(key)})")
            return 0
        write_secret(path, key)
    except OSError as failed:
        say(unusable(failed))
        return BROKEN
    replaced = f", replaced key id {key_id(old)}" if old else ""
    say(f"HERD_SECRET_KEY written (key id {key_id(key)}{replaced}); start the stack again")
    return 0
