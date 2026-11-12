"""URL slugs from human titles (German umlauts transliterated)."""

import re
import unicodedata

_TRANSLIT = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"}
)


def slugify(value: str, *, max_length: int = 80) -> str:
    value = value.translate(_TRANSLIT)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:max_length].strip("-") or "untitled"
