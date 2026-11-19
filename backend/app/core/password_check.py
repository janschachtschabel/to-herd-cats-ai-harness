"""Whether a new password is easy to guess (ASVS 5.0 V6.2.4, V6.2.11, V6.2.12).

Two checks, after the length rule (`password_rule.py`) and before hashing; any
composition of characters stays allowed (V6.2.5):

- Breached passwords: `common_passwords.txt.gz` holds the 142,518 most frequent
  passwords of 10 to 200 characters from the top million of Pwdb-Public
  (github.com/ignis-sec/Pwdb-Public, MIT, via SecLists
  `Passwords/Common-Credentials/Pwdb_top-1000000.txt`, MIT), lower-cased and without
  repeats, most frequent first. Compared without regard to case. The file is read only
  when a password is set (off the event loop) and never kept in memory.
- Context words (documented in docs/SICHERHEIT.md): the product's names, the
  organisation's name and the person's email (local part, domain label) and name; a
  word of four or more letters or digits may not appear in the password, compared
  without case, spaces or punctuation.
"""

import asyncio
import gzip
import re
from collections.abc import Iterable
from pathlib import Path

from app.core.errors import ValidationFailed

COMMON_FILE = Path(__file__).with_name("common_passwords.txt.gz")
PRODUCT_WORDS = ("toherdcats", "herdcats")
MIN_CONTEXT_WORD = 4
_NOT_ALNUM = re.compile(r"[\W_]+")


def _letters(text: str) -> str:
    return _NOT_ALNUM.sub("", text.lower())


def context_words(*, org_name: str, email: str, name: str) -> list[str]:
    """The words of the context a person's password may not contain."""
    local, _, domain = email.partition("@")
    parts = [org_name, local, domain.split(".")[0], name, *name.split(), *local.split(".")]
    return [*PRODUCT_WORDS, *parts]


def _breached(password: str) -> bool:
    with gzip.open(COMMON_FILE, "rt", encoding="utf-8") as f:
        return f"\n{password.lower()}\n" in f"\n{f.read()}"


async def refuse_guessable(password: str, context: Iterable[str]) -> None:
    """422 `auth.password_context` or `auth.password_common` for a guessable password."""
    letters = _letters(password)
    for word in map(_letters, context):
        if len(word) >= MIN_CONTEXT_WORD and word in letters:
            raise ValidationFailed(code="auth.password_context")
    if await asyncio.to_thread(_breached, password):
        raise ValidationFailed(code="auth.password_common")
