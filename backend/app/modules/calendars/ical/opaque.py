"""The UID a redacted event is written under (review M10 Task 7a, R7a-5; decision 3:
"nur Zeit und Belegt"): a keyed hash of its real UID, so whoever sees only "busy"
cannot confirm a guessed UID (a meeting platform's numbered ones, a booking code), and
two readers' copies cannot be joined on it.

`opaque_uid(uid, key=, audience=)` is HMAC-SHA-256 under `key` over the reader
(`audience`: the feed's id for a feed, the person's id for an export) and the UID,
the first 128 bits in hex, `@busy.invalid`. Stable for one reader across fetches.

The key: `key_from_secret(HERD_SECRET_KEY)`, HKDF-SHA256 with the fixed label
`KEY_INFO` (32 bytes), derived where the secret is read (Tasks 7b and 8a), never
stored. Rotating `HERD_SECRET_KEY` gives every busy block a new UID once.
"""

import hashlib
import hmac

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_INFO = b"to-herd-cats-ai:calendar:opaque-uid:v1"
_HEX = 32  # 128 bits
DOMAIN = "busy.invalid"


def key_from_secret(secret: str) -> bytes:
    """The key for `opaque_uid`, derived from the installation's secret key."""
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=KEY_INFO).derive(
        secret.encode()
    )


def opaque_uid(uid: str, *, key: bytes, audience: str) -> str:
    if len(key) < 32:
        raise ValueError("the key is 32 bytes from key_from_secret")
    message = audience.encode() + b"\x00" + uid.encode()
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()[:_HEX]
    return f"{digest}@{DOMAIN}"
