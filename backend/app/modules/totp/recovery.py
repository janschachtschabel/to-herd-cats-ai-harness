"""Recovery codes (ASVS 5.0 V6.5.2 to V6.5.4): ten per set, each 120 bits from the
CSPRNG in base32 (24 characters, shown in four groups of six). With 112 bits or more a
plain SHA-256 may store them (V6.5.2), so a code is found by its hash in one
statement. Spaces, dashes and case do not matter when one is typed."""

import base64
import hashlib
import secrets

CODES_PER_SET = 10
_CODE_BYTES = 15  # 120 bits = 24 base32 characters, no padding
_GROUP = 6


def new_codes() -> list[str]:
    return [
        _format(base64.b32encode(secrets.token_bytes(_CODE_BYTES)).decode())
        for _ in range(CODES_PER_SET)
    ]


def digest(code: str) -> str:
    """The stored form of a code as typed."""
    return hashlib.sha256(_normalised(code).encode()).hexdigest()


def _normalised(code: str) -> str:
    return "".join(ch for ch in code if not ch.isspace() and ch != "-").upper()


def _format(raw: str) -> str:
    return "-".join(raw[i : i + _GROUP] for i in range(0, len(raw), _GROUP))
