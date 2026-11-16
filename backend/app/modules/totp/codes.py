"""Time-based one-time passwords (RFC 6238) on HOTP (RFC 4226), with `hmac` only.

The app's parameters are the ones every authenticator app reads from an `otpauth://`
URI without asking: SHA-1, 6 digits, a 30-second step. A secret is 160 random bits
from the CSPRNG (`secrets`), the length RFC 4226 recommends, written in base32 without
padding (32 characters). A code is accepted for its step and one step on either side
(clocks drift and typing takes time), never further; that a step is used only once is
the caller's rule (`repository.TotpRepository.use_step`).
"""

import base64
import hashlib
import hmac
import re
import secrets
from urllib.parse import quote, urlencode

STEP_SECONDS = 30
DIGITS = 6
WINDOW = 1  # steps accepted before and after the current one
SECRET_BYTES = 20
_ALGORITHMS = {"sha1": hashlib.sha1, "sha256": hashlib.sha256, "sha512": hashlib.sha512}
_CODE = re.compile(r"[0-9]{6}")


def hotp(key: bytes, counter: int, *, digits: int = DIGITS, algorithm: str = "sha1") -> str:
    """RFC 4226 section 5.3: dynamic truncation of HMAC(key, counter)."""
    mac = hmac.new(key, counter.to_bytes(8, "big"), _ALGORITHMS[algorithm]).digest()
    offset = mac[-1] & 0x0F
    value = int.from_bytes(mac[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def step_at(unix_time: float) -> int:
    """The RFC 6238 time step (T0 = 0) a moment falls in."""
    return int(unix_time // STEP_SECONDS)


def matching_step(secret: str, code: str, unix_time: float) -> int | None:
    """The step within the window whose code `code` is, or None. Spaces are ignored;
    anything but six ASCII digits never matches. Every step of the window is compared
    in constant time, whichever matches."""
    typed = "".join(code.split())
    if not _CODE.fullmatch(typed):
        return None
    key = _key(secret)
    current = step_at(unix_time)
    found = None
    for step in range(current - WINDOW, current + WINDOW + 1):
        if hmac.compare_digest(hotp(key, step), typed) and found is None:
            found = step
    return found


def new_secret() -> str:
    """160 bits from the CSPRNG, base32 without padding (ASVS 5.0 V6.5.3)."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode().rstrip("=")


def otpauth_uri(secret: str, *, account: str, issuer: str) -> str:
    """The Key URI authenticator apps import (as a QR code or typed)."""
    label = f"{quote(issuer, safe='')}:{quote(account, safe='')}"
    query = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": STEP_SECONDS,
        },
        quote_via=quote,
    )
    return f"otpauth://totp/{label}?{query}"


def _key(secret: str) -> bytes:
    padding = "=" * (-len(secret) % 8)
    return base64.b32decode(secret + padding)
