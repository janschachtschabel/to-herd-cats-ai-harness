"""Files in an S3-compatible store (plan M9 decision 18, `HERD_STORAGE=s3`): the
`Storage` protocol over `s3_client.S3Client`.

Keys are checked like local ones and go under `HERD_S3_PREFIX`. A write stores the
content's SHA-256 as `x-amz-meta-sha256`, so `stat` (a restore's check, a copy) knows
it without reading the object.

Outbound requests pass the egress guard (`core/egress.py`): the endpoint is the
operator's setting, so its host (a name, or a private address written as such) is the
one private target the rules allow; link-local and metadata addresses stay refused,
redirects are never followed, and no proxy from the environment is used. One HTTP
client per event loop is shared by every `S3Storage` of that loop.
"""

import ipaddress
import logging
import weakref
from asyncio import AbstractEventLoop, get_running_loop
from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import httpx

from app.core import egress
from app.core.config import Settings
from app.core.egress import EgressRules
from app.core.egress_allowance import PRIVATE_RANGES, host_key
from app.core.s3_client import ContentMismatch, S3Client, S3Failed
from app.core.storage import (
    CHUNK,
    StorageKeyError,
    StorageUnavailable,
    StoredContentMismatch,
    StoredFile,
    StoredFileMissing,
    valid_key,
)

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60.0  # one request, an attachment up to its limit included
SHA256_META = "sha256"

_clients: "weakref.WeakKeyDictionary[AbstractEventLoop, dict[str, httpx.AsyncClient]]" = (
    weakref.WeakKeyDictionary()
)


def endpoint_rules(endpoint: str) -> EgressRules:
    """The egress rules for the store: http and https, private targets only at the
    endpoint's own host."""
    host = urlsplit(endpoint).hostname or ""
    rules = EgressRules(allow_private=False, allow_http=True)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return EgressRules(
            allow_private=False, allow_http=True, private_hosts=frozenset({host_key(host)})
        )
    if any(address.version == r.version and address in r for r in PRIVATE_RANGES):
        return EgressRules(
            allow_private=False, allow_http=True, private_networks=(ipaddress.ip_network(address),)
        )
    return rules


def _http_client(endpoint: str) -> httpx.AsyncClient:
    per_loop = _clients.setdefault(get_running_loop(), {})
    client = per_loop.get(endpoint)
    if client is None or client.is_closed:
        client = egress.client(endpoint_rules(endpoint), timeout=TIMEOUT_SECONDS)
        per_loop[endpoint] = client
    return client


def s3_storage(settings: Settings) -> "S3Storage":
    client = S3Client(
        endpoint=settings.s3_endpoint,
        region=settings.s3_region,
        bucket=settings.s3_bucket,
        credentials=settings.s3_credentials(),
        http=_http_client(settings.s3_endpoint),
    )
    return S3Storage(client, settings.s3_prefix)


def _unavailable(failed: S3Failed, operation: str) -> StorageUnavailable:
    logger.warning(
        "storage.s3_failed",
        extra={"operation": operation, "code": failed.code, "status": failed.status},
    )
    return StorageUnavailable(failed.code)


class S3Storage:
    def __init__(self, client: S3Client, prefix: str = "") -> None:
        self.client = client
        self.prefix = f"{prefix}/" if prefix else ""

    def object_key(self, key: str) -> str:
        if not valid_key(key):
            raise StorageKeyError("invalid storage key")
        return self.prefix + key

    async def put(self, key: str, data: AsyncIterator[bytes], *, size: int, sha256: str) -> int:
        name = self.object_key(key)
        try:
            await self.client.put_object(
                name, data, size=size, sha256=sha256, meta={SHA256_META: sha256}
            )
        except ContentMismatch:
            raise StoredContentMismatch(key) from None
        except S3Failed as failed:
            raise _unavailable(failed, "put") from None
        return size

    async def open(self, key: str) -> AsyncIterator[bytes]:
        name = self.object_key(key)
        try:
            response = await self.client.get_object(name)
        except S3Failed as failed:
            raise _unavailable(failed, "get") from None
        if response is None:
            raise StoredFileMissing(key)
        return _body(response)

    async def delete(self, key: str) -> None:
        try:
            await self.client.delete_object(self.object_key(key))
        except S3Failed as failed:
            raise _unavailable(failed, "delete") from None

    async def exists(self, key: str) -> bool:
        return await self.stat(key) is not None

    async def stat(self, key: str) -> StoredFile | None:
        try:
            info = await self.client.head_object(self.object_key(key))
        except S3Failed as failed:
            raise _unavailable(failed, "head") from None
        if info is None:
            return None
        return StoredFile(info.size, info.meta.get(SHA256_META))

    async def entries(self, prefix: str) -> AsyncIterator[tuple[str, int]]:
        if prefix and not valid_key(prefix):
            raise StorageKeyError("invalid storage key")
        start = self.prefix + (f"{prefix}/" if prefix else "")
        try:
            async for name, size in self.client.list_objects(start):
                key = name.removeprefix(self.prefix)
                if valid_key(key):
                    yield key, size
        except S3Failed as failed:
            raise _unavailable(failed, "list") from None


async def _body(response: httpx.Response) -> AsyncIterator[bytes]:
    try:
        async for chunk in response.aiter_bytes(CHUNK):
            yield chunk
    except httpx.TransportError:
        raise StorageUnavailable("s3.unreachable") from None
    finally:
        await response.aclose()
