"""The UID a redacted event is written under (review M10 Task 7a, R7a-5; decision 3:
"nur Zeit und Belegt"): a keyed hash of its real UID, so whoever sees only "busy"
cannot confirm a guessed UID (a meeting platform's numbered ones, a booking code), and
two readers' copies cannot be joined on it.

`opaque_uid(uid, key=, purpose=, audience=)` is HMAC-SHA-256 under `key` over a fixed
label, the purpose (`Purpose.FEED` with the feed's id as `audience`, `Purpose.EXPORT`
with the exporting person's id), the audience and the UID, each part length-prefixed
(re-check RC7a-9: a feed's id and a person's id never share a name space, and no part
runs into the next); the first 128 bits in hex, `@busy.invalid`. Stable for one reader
across fetches.

The key: `key_from_secret(HERD_SECRET_KEY)`, HKDF-SHA256 with the fixed label
`KEY_INFO` (32 bytes), derived where the secret is read (Tasks 7b and 8a), never
stored; an empty secret is refused. Rotating `HERD_SECRET_KEY` gives every busy block a
new UID once.
"""

import hashlib
import hmac
from enum import StrEnum

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_INFO = b"to-herd-cats-ai:calendar:opaque-uid:v1"
_LABEL = b"to-herd-cats-ai:calendar:opaque-uid:message:v1"
_HEX = 32  # 128 bits
DOMAIN = "busy.invalid"


class Purpose(StrEnum):
    FEED = "feed"  # audience: the feed's id (Task 8a)
    EXPORT = "export"  # audience: the exporting person's id (Task 7b)


def key_from_secret(secret: str) -> bytes:
    """The key for `opaque_uid`, derived from the installation's secret key; an empty
    one is refused (an unset `HERD_SECRET_KEY` must not give a key anyone can compute)."""
    if not secret:
        raise ValueError("an empty secret gives no key")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=KEY_INFO).derive(
        secret.encode()
    )


def _part(data: bytes) -> bytes:
    return len(data).to_bytes(4, "big") + data


def opaque_uid(uid: str, *, key: bytes, purpose: Purpose, audience: str) -> str:
    if len(key) < 32:
        raise ValueError("the key is 32 bytes from key_from_secret")
    message = b"".join(
        _part(part) for part in (_LABEL, Purpose(purpose).encode(), audience.encode(), uid.encode())
    )
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()[:_HEX]
    return f"{digest}@{DOMAIN}"
