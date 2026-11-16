"""A small S3 client on httpx (plan M9 decision 18; no boto): path-style requests
signed with SigV4 (`s3_signing.py`), PUT with the payload's known SHA-256 as
`x-amz-content-sha256` and a Content-Length (no chunked upload), GET streamed, HEAD,
DELETE and ListObjectsV2.

The HTTP client comes from the caller (`storage_s3.py` builds one through the egress
guard). Failures are `S3Failed` with a fixed code and the HTTP status, never a URL,
header or body: `s3.unreachable` (no connection, a timeout), `s3.blocked` (the egress
guard refused the address), `s3.denied` (401/403: keys, signature, clock),
`s3.no_bucket`, `s3.content_mismatch` (the store found other bytes than the declared
SHA-256), `s3.refused` (another 4xx), `s3.failed` (5xx), `s3.bad_answer` (a list it
cannot read).

A PUT counts the bytes and hashes them while it sends; the last chunk is held back
until the whole content is known to match, so content that does not match its SHA-256
or size is never sent whole and the store keeps nothing (`ContentMismatch`).
"""

import hashlib
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterable, AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from app.core.egress import EgressBlocked
from app.core.s3_signing import Credentials, amz_date, canonical_path, canonical_query, sign

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
LIST_PAGE = 1000
_LIST_MAX_BYTES = 8 * 1024 * 1024
_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


class S3Failed(Exception):
    def __init__(self, code: str, status: int | None = None) -> None:
        super().__init__(code if status is None else f"{code} ({status})")
        self.code = code
        self.status = status


class ContentMismatch(Exception):  # noqa: N818 (a verdict)
    """The bytes handed to a PUT are not the declared size or SHA-256."""


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    meta: dict[str, str]


def _now() -> datetime:
    return datetime.now(UTC)


class S3Client:
    def __init__(
        self,
        *,
        endpoint: str,
        region: str,
        bucket: str,
        credentials: Credentials,
        http: httpx.AsyncClient,
        now: Callable[[], datetime] = _now,
    ) -> None:
        parts = urlsplit(endpoint)
        self._base = f"{parts.scheme}://{parts.netloc}"
        self._host = parts.netloc
        self._region = region
        self._bucket = bucket
        self._credentials = credentials
        self._http = http
        self._now = now

    def _request(
        self,
        method: str,
        key: str,
        *,
        query: list[tuple[str, str]] | None = None,
        payload_sha256: str = EMPTY_SHA256,
        headers: Mapping[str, str] | None = None,
        content: AsyncIterable[bytes] | None = None,
    ) -> httpx.Request:
        path = f"/{self._bucket}/{key}" if key else f"/{self._bucket}"
        at = self._now()
        signed = {
            **(headers or {}),
            "x-amz-content-sha256": payload_sha256,
            "x-amz-date": amz_date(at),
        }
        authorization = sign(
            method=method,
            host=self._host,
            path=path,
            query=query or [],
            headers=signed,
            payload_sha256=payload_sha256,
            credentials=self._credentials,
            region=self._region,
            at=at,
        )
        url = self._base + canonical_path(path)
        if query:
            url += "?" + canonical_query(query)
        return self._http.build_request(
            method,
            url,
            headers={**signed, "host": self._host, "authorization": authorization},
            content=content,
        )

    async def _send(self, request: httpx.Request, *, stream: bool = False) -> httpx.Response:
        try:
            return await self._http.send(request, stream=stream)
        except EgressBlocked:
            raise S3Failed("s3.blocked") from None
        except httpx.TransportError:
            raise S3Failed("s3.unreachable") from None

    async def put_object(
        self,
        key: str,
        chunks: AsyncIterator[bytes],
        *,
        size: int,
        sha256: str,
        meta: Mapping[str, str],
    ) -> None:
        headers = {"content-length": str(size), **{f"x-amz-meta-{k}": v for k, v in meta.items()}}
        if size == 0:
            await _drain_empty(chunks, sha256)
            body = None
        else:
            body = _checked(chunks, size, sha256)
        request = self._request("PUT", key, payload_sha256=sha256, headers=headers, content=body)
        try:
            response = await self._send(request)
        except S3Failed:
            if isinstance(body, _checked) and body.mismatch:
                raise ContentMismatch from None
            raise
        _raise_for(response, mismatch_is_content=True)

    async def get_object(self, key: str) -> httpx.Response | None:
        """The open, streamed answer (the caller closes it), or None when there is no
        object under `key`."""
        response = await self._send(self._request("GET", key), stream=True)
        if response.status_code == 200:
            return response
        body = await _small(response)
        if response.status_code == 404 and _code_of(body) != "NoSuchBucket":
            return None
        _raise_for(response, body)
        return None  # pragma: no cover (_raise_for raised)

    async def head_object(self, key: str) -> ObjectInfo | None:
        response = await self._send(self._request("HEAD", key))
        if response.status_code == 404:
            return None
        _raise_for(response)
        meta = {
            k.removeprefix("x-amz-meta-"): v
            for k, v in response.headers.items()
            if k.startswith("x-amz-meta-")
        }
        return ObjectInfo(int(response.headers.get("content-length", "0")), meta)

    async def delete_object(self, key: str) -> None:
        response = await self._send(self._request("DELETE", key))
        if response.status_code != 404:
            _raise_for(response)

    async def list_objects(self, prefix: str) -> AsyncIterator[tuple[str, int]]:
        """Every key under `prefix` with its size, page by page (ListObjectsV2)."""
        token: str | None = None
        while True:
            query = [("list-type", "2"), ("max-keys", str(LIST_PAGE)), ("prefix", prefix)]
            if token is not None:
                query.append(("continuation-token", token))
            response = await self._send(self._request("GET", "", query=query), stream=True)
            body = await _small(response, _LIST_MAX_BYTES)
            _raise_for(response, body)
            entries, token = _parse_list(body)
            for entry in entries:
                yield entry
            if token is None:
                return


class _checked:  # noqa: N801 (an async iterator handed to httpx)
    """The chunks, counted and hashed; the last one is held back until the content is
    known to match (`mismatch` is set otherwise and the body ends early)."""

    def __init__(self, chunks: AsyncIterator[bytes], size: int, sha256: str) -> None:
        self._chunks = chunks
        self._size = size
        self._sha256 = sha256
        self.mismatch = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        digest, seen, held = hashlib.sha256(), 0, b""
        async for chunk in self._chunks:
            if not chunk:
                continue
            digest.update(chunk)
            seen += len(chunk)
            if seen > self._size:
                break
            if held:
                yield held
            held = chunk
        if seen != self._size or digest.hexdigest() != self._sha256:
            self.mismatch = True
            raise ContentMismatch
        yield held


async def _drain_empty(chunks: AsyncIterator[bytes], sha256: str) -> None:
    async for chunk in chunks:
        if chunk:
            raise ContentMismatch
    if sha256 != EMPTY_SHA256:
        raise ContentMismatch


async def _small(response: httpx.Response, limit: int = 64 * 1024) -> bytes:
    """At most `limit` bytes of an answer's body; the answer is closed."""
    data = b""
    try:
        async for chunk in response.aiter_bytes():
            data += chunk
            if len(data) > limit:
                raise S3Failed("s3.bad_answer", response.status_code)
    except httpx.TransportError:
        raise S3Failed("s3.unreachable") from None
    finally:
        await response.aclose()
    return data


def _code_of(body: bytes) -> str | None:
    try:
        return ET.fromstring(body).findtext("Code")  # noqa: S314 (the operator's store)
    except ET.ParseError:
        return None


def _raise_for(
    response: httpx.Response, body: bytes | None = None, *, mismatch_is_content: bool = False
) -> None:
    """Nothing for a 2xx answer, else the failure; `body` for a streamed answer (read
    by `_small`), a plain one has its content read."""
    status = response.status_code
    if 200 <= status < 300:
        return
    code = _code_of(response.content if body is None else body)
    if status in (401, 403):
        raise S3Failed("s3.denied", status)
    if code == "NoSuchBucket":
        raise S3Failed("s3.no_bucket", status)
    if mismatch_is_content and code in ("XAmzContentSHA256Mismatch", "BadDigest"):
        raise ContentMismatch
    raise S3Failed("s3.refused" if status < 500 else "s3.failed", status)


def _parse_list(body: bytes) -> tuple[list[tuple[str, int]], str | None]:
    try:
        root = ET.fromstring(body)  # noqa: S314 (the operator's store)
        entries = [
            (item.findtext(f"{_NS}Key") or "", int(item.findtext(f"{_NS}Size") or "0"))
            for item in root.iter(f"{_NS}Contents")
        ]
        truncated = (root.findtext(f"{_NS}IsTruncated") or "").lower() == "true"
        token = root.findtext(f"{_NS}NextContinuationToken")
    except (ET.ParseError, ValueError):
        raise S3Failed("s3.bad_answer") from None
    if truncated and not token:
        raise S3Failed("s3.bad_answer")
    return [e for e in entries if e[0]], token if truncated else None
