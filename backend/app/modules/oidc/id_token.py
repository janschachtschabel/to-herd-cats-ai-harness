"""Checking an ID token (plan M9 decision 12; OpenID Connect Core 3.1.3.7) with PyJWT.

- Algorithms RS256 and ES256 only, taken from the header before anything else: `none`
  and every HMAC algorithm are refused (an HMAC "signed" with the public key is the
  classic confusion). The key is the provider's JWKS entry with the header's `kid`,
  of the matching key type, not meant for encryption, and with the same `alg` if it
  names one; none: `kid_unknown` (the caller may fetch the JWKS again).
- `iss` exactly one of the provider's issuers; `aud` holds the client id; with more
  than one audience `azp` must be the client id, and a present `azp` always is.
- `exp`, `iat` (and `nbf` when present) against `now` with `LEEWAY`; the clock is the
  caller's (`core/clock.py` in the flow), never PyJWT's.
- `nonce` equal to the one the flow sent.

Failures are `IdTokenInvalid(reason)` with a fixed word; neither the token nor a claim
goes into the exception, a log line or an answer.
"""

import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import jwt

ALGORITHMS = {"RS256": "RSA", "ES256": "EC"}
LEEWAY = timedelta(seconds=60)
MAX_SUBJECT_CHARS = 255
MAX_TOKEN_CHARS = 16_384


class IdTokenInvalid(Exception):  # noqa: N818 (a verdict)
    """`reason`: signature, alg, iss, aud, azp, expired, not_yet_valid, nonce,
    kid_unknown or malformed."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"id token invalid: {reason}")


@dataclass(frozen=True, slots=True)
class IdClaims:
    """What sign-in reads of a checked token; `email` lower case, `hd` as sent."""

    sub: str
    email: str | None
    email_verified: bool
    hd: str | None
    name: str | None
    locale: str | None
    # When the person last authenticated at the provider (epoch seconds), if it says.
    auth_time: float | None = None


def verify_id_token(
    raw: str,
    *,
    jwks: Mapping[str, Any],
    issuers: frozenset[str],
    client_id: str,
    nonce: str,
    now: datetime,
) -> IdClaims:
    if len(raw) > MAX_TOKEN_CHARS:
        raise IdTokenInvalid("malformed")
    try:
        header = jwt.get_unverified_header(raw)
    except jwt.PyJWTError:
        raise IdTokenInvalid("malformed") from None
    alg = header.get("alg")
    if not isinstance(alg, str) or alg not in ALGORITHMS:
        raise IdTokenInvalid("alg")
    key = _key(jwks, header.get("kid"), alg)
    try:
        claims = jwt.decode(
            raw,
            key,
            algorithms=[alg],
            options={
                "verify_signature": True,
                "verify_exp": False,
                "verify_nbf": False,
                "verify_iat": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except jwt.InvalidSignatureError:
        raise IdTokenInvalid("signature") from None
    except jwt.PyJWTError:
        raise IdTokenInvalid("malformed") from None
    _check(claims, issuers=issuers, client_id=client_id, nonce=nonce, now=now)
    return _claims(claims)


def _key(jwks: Mapping[str, Any], kid: object, alg: str) -> jwt.PyJWK:
    keys = jwks.get("keys")
    candidates = [
        entry
        for entry in (keys if isinstance(keys, list) else [])
        if isinstance(entry, dict)
        and entry.get("kty") == ALGORITHMS[alg]
        and entry.get("use", "sig") == "sig"
        and entry.get("alg", alg) == alg
        and (entry.get("kid") == kid if kid is not None else True)
    ]
    if len(candidates) != 1:  # none, or no `kid` and no single key to take
        raise IdTokenInvalid("kid_unknown")
    try:
        return jwt.PyJWK(candidates[0], algorithm=alg)
    except jwt.PyJWTError:
        raise IdTokenInvalid("kid_unknown") from None


def _number(claims: Mapping[str, Any], name: str, *, required: bool) -> float | None:
    value = claims.get(name)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise IdTokenInvalid("malformed")
    return float(value)


def _check(
    claims: Mapping[str, Any],
    *,
    issuers: frozenset[str],
    client_id: str,
    nonce: str,
    now: datetime,
) -> None:
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub or len(sub) > MAX_SUBJECT_CHARS:
        raise IdTokenInvalid("malformed")
    exp = _number(claims, "exp", required=True)
    iat = _number(claims, "iat", required=True)
    nbf = _number(claims, "nbf", required=False)
    if claims.get("iss") not in issuers:
        raise IdTokenInvalid("iss")
    aud = claims.get("aud")
    audiences = [aud] if isinstance(aud, str) else aud if isinstance(aud, list) else []
    if client_id not in audiences:
        raise IdTokenInvalid("aud")
    azp = claims.get("azp")
    if (len(audiences) > 1 or azp is not None) and azp != client_id:
        raise IdTokenInvalid("azp")
    moment = now.timestamp()
    leeway = LEEWAY.total_seconds()
    assert exp is not None and iat is not None
    if moment > exp + leeway:
        raise IdTokenInvalid("expired")
    if iat > moment + leeway or (nbf is not None and nbf > moment + leeway):
        raise IdTokenInvalid("not_yet_valid")
    sent = claims.get("nonce")
    if not isinstance(sent, str) or not hmac.compare_digest(sent.encode(), nonce.encode()):
        raise IdTokenInvalid("nonce")


def _text(claims: Mapping[str, Any], name: str, limit: int) -> str | None:
    value = claims.get(name)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] if value else None


def _claims(claims: Mapping[str, Any]) -> IdClaims:
    verified = claims.get("email_verified")
    email = _text(claims, "email", 254)
    return IdClaims(
        sub=claims["sub"],
        email=email.lower() if email else None,
        email_verified=verified is True or verified == "true",
        hd=_text(claims, "hd", 253),
        name=_text(claims, "name", 120),
        locale=_text(claims, "locale", 16),
        auth_time=_number(claims, "auth_time", required=False),
    )
