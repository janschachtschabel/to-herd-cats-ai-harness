"""Attachments in an S3-compatible store (plan M9 task 14, decision 18), against the
local stub that checks every signature: the storage protocol, refusals, the prefix,
listing across pages, the egress guard, and content that does not match its SHA-256
never stored."""

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core import egress
from app.core.s3_client import S3Client
from app.core.s3_signing import Credentials
from app.core.storage import (
    StorageKeyError,
    StorageUnavailable,
    StoredContentMismatch,
    StoredFileMissing,
    get_storage,
    stored_sha256,
)
from app.core.storage_s3 import S3Storage, endpoint_rules
from tests.factories_s3 import s3_settings_for
from tests.support.s3_stub import ACCESS_KEY, BUCKET, S3Stub

KEY = "attachments/0b9e5f0c-0000-4000-8000-000000000001/abc"


async def _chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _read(storage: S3Storage, key: str) -> bytes:
    return b"".join([chunk async for chunk in await storage.open(key)])


def _storage(stub: S3Stub, **changes: object) -> S3Storage:
    storage = get_storage(s3_settings_for(stub, **changes))
    assert isinstance(storage, S3Storage)
    return storage


async def test_s3_storage_put_open_delete_exists(s3_stub: S3Stub) -> None:
    storage = _storage(s3_stub)
    data = b"x" * 200_000 + b"end"
    assert not await storage.exists(KEY)
    assert await storage.put(
        KEY, _chunks(data[:70_000], data[70_000:]), size=len(data), sha256=_sha(data)
    ) == len(data)
    assert await storage.exists(KEY)
    assert await _read(storage, KEY) == data
    info = await storage.stat(KEY)
    assert info is not None and (info.size, info.sha256) == (len(data), _sha(data))
    assert s3_stub.state.objects[KEY].meta == {"x-amz-meta-sha256": _sha(data)}
    put = next(e for e in s3_stub.state.log if e.method == "PUT")
    assert put.headers["content-length"] == str(len(data))
    assert "transfer-encoding" not in put.headers
    assert put.headers["x-amz-content-sha256"] == _sha(data)
    assert put.path == f"/{BUCKET}/{KEY}"

    await storage.delete(KEY)
    await storage.delete(KEY)  # nothing there is fine
    assert not await storage.exists(KEY)
    with pytest.raises(StoredFileMissing):
        await storage.open(KEY)
    assert await storage.stat(KEY) is None


async def test_an_empty_file_round_trips(s3_stub: S3Stub) -> None:
    storage = _storage(s3_stub)
    await storage.put(KEY, _chunks(), size=0, sha256=_sha(b""))
    assert await _read(storage, KEY) == b""


@pytest.mark.parametrize(
    "parts",
    [(b"hello", b" world"), (b"hello",), (b"hello", b" world", b"!")],
    ids=["other-bytes", "too-short", "too-long"],
)
async def test_content_that_does_not_match_is_never_stored(
    s3_stub: S3Stub, parts: tuple[bytes, ...]
) -> None:
    storage = _storage(s3_stub)
    declared = b"hello there"
    with pytest.raises(StoredContentMismatch):
        await storage.put(KEY, _chunks(*parts), size=len(declared), sha256=_sha(declared))
    assert s3_stub.state.objects == {}


async def test_the_prefix_keeps_keys_apart(s3_stub: S3Stub) -> None:
    storage = _storage(s3_stub, s3_prefix="herd/prod/")
    await storage.put(KEY, _chunks(b"a"), size=1, sha256=_sha(b"a"))
    assert list(s3_stub.state.objects) == [f"herd/prod/{KEY}"]
    assert [k async for k, _ in storage.entries("attachments")] == [KEY]
    assert await stored_sha256(storage, KEY) == _sha(b"a")


async def test_entries_list_across_pages(s3_stub: S3Stub) -> None:
    storage = _storage(s3_stub)
    keys = [f"attachments/org/{i:03d}" for i in range(7)]
    for key in keys:
        await storage.put(key, _chunks(key.encode()), size=len(key), sha256=_sha(key.encode()))
    await storage.put("other/x", _chunks(b"o"), size=1, sha256=_sha(b"o"))
    s3_stub.state.max_keys = 3
    listed = [entry async for entry in storage.entries("attachments")]
    assert listed == [(k, len(k)) for k in keys]
    lists = [e for e in s3_stub.state.log if e.method == "GET" and "list-type=2" in e.query]
    assert len(lists) == 3


async def test_keys_are_checked_like_local_ones(s3_stub: S3Stub) -> None:
    storage = _storage(s3_stub)
    for bad in ("../x", "/abs", "Attachments/x", "a//b", ""):
        with pytest.raises(StorageKeyError):
            await storage.exists(bad)


async def test_a_wrong_signature_is_refused_by_the_stub(s3_stub: S3Stub) -> None:
    storage = _storage(s3_stub, s3_secret_access_key="not-the-secret-key")
    with pytest.raises(StorageUnavailable) as refused:
        await storage.put(KEY, _chunks(b"a"), size=1, sha256=_sha(b"a"))
    assert refused.value.reason == "s3.denied"
    assert refused.value.status_code == 503 and refused.value.code == "storage.unavailable"
    assert s3_stub.state.objects == {}

    # the request as signed, then changed on the way: refused too
    good = _storage(s3_stub)
    request = good.client._request("GET", KEY)
    tampered = httpx.Request("GET", str(request.url) + "x", headers=request.headers)
    async with httpx.AsyncClient() as plain:
        answer = await plain.send(tampered)
    assert answer.status_code == 403 and b"SignatureDoesNotMatch" in answer.content


async def test_a_request_from_the_past_is_refused(s3_stub: S3Stub) -> None:
    async with egress.client(endpoint_rules(s3_stub.url), timeout=5) as http:
        old = S3Client(
            endpoint=s3_stub.url,
            region="us-east-1",
            bucket=BUCKET,
            credentials=Credentials(ACCESS_KEY, "herd-stub-secret-key-0123456789abcdef"),
            http=http,
            now=lambda: datetime.now(UTC) - timedelta(hours=1),
        )
        with pytest.raises(Exception, match="s3.denied"):
            await old.head_object(KEY)


async def test_failures_answer_storage_unavailable(s3_stub: S3Stub) -> None:
    storage = _storage(s3_stub)
    s3_stub.state.failures.append(500)
    with pytest.raises(StorageUnavailable) as failed:
        await storage.open(KEY)
    assert failed.value.reason == "s3.failed"
    unknown = _storage(s3_stub, s3_bucket="no-such-bucket")
    with pytest.raises(StorageUnavailable) as missing:
        await unknown.put(KEY, _chunks(b"a"), size=1, sha256=_sha(b"a"))
    assert missing.value.reason == "s3.no_bucket"


async def test_an_unreachable_store_answers_storage_unavailable(s3_stub: S3Stub) -> None:
    storage = _storage(s3_stub, s3_endpoint="http://127.0.0.1:9")
    with pytest.raises(StorageUnavailable) as failed:
        await storage.exists(KEY)
    assert failed.value.reason == "s3.unreachable"


@pytest.mark.parametrize(
    "endpoint", ["http://169.254.169.254", "http://[fe80::1]:8333", "http://0.0.0.0:8333"]
)
async def test_the_egress_guard_refuses_metadata_and_link_local_addresses(
    s3_stub: S3Stub, endpoint: str
) -> None:
    storage = _storage(s3_stub, s3_endpoint=endpoint)
    with pytest.raises(StorageUnavailable) as blocked:
        await storage.exists(KEY)
    assert blocked.value.reason == "s3.blocked"


def test_only_the_endpoint_host_is_an_allowed_private_target() -> None:
    by_name = endpoint_rules("http://seaweedfs:8333")
    assert by_name.private_hosts == frozenset({"seaweedfs"})
    assert not by_name.allow_private and by_name.allow_http
    by_address = endpoint_rules("http://10.1.2.3:8333")
    assert [str(n) for n in by_address.private_networks] == ["10.1.2.3/32"]
    public = endpoint_rules("https://203.0.113.9")
    assert public.private_hosts == frozenset() and public.private_networks == ()
