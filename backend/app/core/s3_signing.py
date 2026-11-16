"""AWS Signature Version 4 for S3 requests (plan M9 decision 18), header form, payload
in one piece (its SHA-256 is known before sending: `x-amz-content-sha256`).

Pure functions: `canonical_request` builds what is signed, `sign` returns the
`Authorization` header. Path segments and query parts are percent-encoded once with
the unreserved characters left as they are (S3 does not encode twice); the `host`
header is always signed. The secret key never leaves `Credentials` other than into the
HMAC (no repr, no logs); `tests/test_s3_signing.py` holds AWS's published examples.
"""

import hashlib
import hmac
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import quote

ALGORITHM = "AWS4-HMAC-SHA256"
_UNRESERVED = "-_.~"


@dataclass(frozen=True)
class Credentials:
    access_key_id: str
    secret_access_key: str = field(repr=False)


def amz_date(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _encode(value: str) -> str:
    return quote(value, safe=_UNRESERVED)


def canonical_path(path: str) -> str:
    return "/".join(_encode(segment) for segment in path.split("/"))


def canonical_query(query: Sequence[tuple[str, str]]) -> str:
    return "&".join(f"{k}={v}" for k, v in sorted((_encode(k), _encode(v)) for k, v in query))


def canonical_request(
    *,
    method: str,
    host: str,
    path: str,
    query: Sequence[tuple[str, str]],
    headers: Mapping[str, str],
    payload_sha256: str,
) -> tuple[str, str]:
    """The canonical request and the list of signed headers."""
    named = {k.lower(): " ".join(v.strip().split()) for k, v in headers.items()}
    named["host"] = host
    names = sorted(named)
    signed = ";".join(names)
    lines = [
        method,
        canonical_path(path),
        canonical_query(query),
        *(f"{name}:{named[name]}" for name in names),
        "",
        signed,
        payload_sha256,
    ]
    return "\n".join(lines), signed


def signing_key(secret: str, day: str, region: str, service: str) -> bytes:
    key = f"AWS4{secret}".encode()
    for part in (day, region, service, "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    return key


def sign(
    *,
    method: str,
    host: str,
    path: str,
    query: Sequence[tuple[str, str]],
    headers: Mapping[str, str],
    payload_sha256: str,
    credentials: Credentials,
    region: str,
    at: datetime,
    service: str = "s3",
) -> str:
    """The `Authorization` header for the request; `headers` must hold the same
    `x-amz-date` as `at` (the caller sends exactly these headers)."""
    request, signed = canonical_request(
        method=method,
        host=host,
        path=path,
        query=query,
        headers=headers,
        payload_sha256=payload_sha256,
    )
    stamp = amz_date(at)
    scope = f"{stamp[:8]}/{region}/{service}/aws4_request"
    to_sign = "\n".join([ALGORITHM, stamp, scope, hashlib.sha256(request.encode()).hexdigest()])
    key = signing_key(credentials.secret_access_key, stamp[:8], region, service)
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    return (
        f"{ALGORITHM} Credential={credentials.access_key_id}/{scope},"
        f"SignedHeaders={signed},Signature={signature}"
    )
