"""The S3 client against a real S3-compatible store (plan M9 task 14), when one is
named: `HERD_TEST_S3_ENDPOINT`, `HERD_TEST_S3_ACCESS_KEY_ID` and
`HERD_TEST_S3_SECRET_ACCESS_KEY` (a local SeaweedFS, `weed server -s3`, docs/
SICHERUNG.md); skipped otherwise. Each test works in a bucket of its own, created
and emptied here. The stub (`tests/support/s3_stub.py`) covers the same behaviour in
every run; this proves the stub's reading of the protocol on a real store."""

import hashlib
import os
import uuid
from collections.abc import AsyncIterator

import pytest

from app.core import s3_client
from app.core.config import Settings
from app.core.storage import StorageUnavailable, StoredContentMismatch, get_storage
from app.core.storage_s3 import S3Storage
from app.ops.storage_copy import check_storage

ENDPOINT = os.environ.get("HERD_TEST_S3_ENDPOINT", "")
pytestmark = pytest.mark.skipif(not ENDPOINT, reason="no S3-compatible store named")


def _settings(bucket: str, **changes: object) -> Settings:
    values: dict[str, object] = {
        "storage": "s3",
        "s3_endpoint": ENDPOINT,
        "s3_bucket": bucket,
        "s3_access_key_id": os.environ.get("HERD_TEST_S3_ACCESS_KEY_ID", ""),
        "s3_secret_access_key": os.environ.get("HERD_TEST_S3_SECRET_ACCESS_KEY", ""),
    }
    return Settings.model_validate(values | changes)


async def _one(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
async def store() -> AsyncIterator[S3Storage]:
    bucket = f"herd-test-{uuid.uuid4().hex[:12]}"
    storage = get_storage(_settings(bucket))
    assert isinstance(storage, S3Storage)
    client = storage.client
    created = await client._http.send(client._request("PUT", ""))
    assert created.status_code == 200, created.status_code
    yield storage
    async for name, _ in client.list_objects(""):
        await client.delete_object(name)
    await client._http.send(client._request("DELETE", ""))


async def test_objects_round_trip(store: S3Storage) -> None:
    data = os.urandom(300_000)
    key = "attachments/org/" + _sha(data)
    await store.put(key, _one(data[:100_000], data[100_000:]), size=len(data), sha256=_sha(data))
    info = await store.stat(key)
    assert info is not None and (info.size, info.sha256) == (len(data), _sha(data))
    assert b"".join([c async for c in await store.open(key)]) == data
    await store.delete(key)
    assert not await store.exists(key)
    await check_storage(store)


async def test_content_that_does_not_match_is_never_stored(store: S3Storage) -> None:
    with pytest.raises(StoredContentMismatch):
        await store.put("attachments/x", _one(b"hello", b"world"), size=10, sha256=_sha(b"x" * 10))
    assert not await store.exists("attachments/x")


async def test_the_store_itself_refuses_a_body_of_another_sha256(store: S3Storage) -> None:
    client = store.client
    request = client._request(
        "PUT",
        "attachments/y",
        payload_sha256=_sha(b"other"),
        headers={"content-length": "5"},
        content=_one(b"hello"),
    )
    answer = await client._http.send(request)
    assert answer.status_code == 400 and b"XAmzContentSHA256Mismatch" in answer.content
    assert not await store.exists("attachments/y")


async def test_listing_goes_across_pages(store: S3Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(s3_client, "LIST_PAGE", 2)
    keys = [f"attachments/org/{i:02d}" for i in range(5)]
    for key in keys:
        await store.put(key, _one(key.encode()), size=len(key), sha256=_sha(key.encode()))
    assert [k async for k, _ in store.entries("attachments")] == keys


async def test_a_wrong_secret_is_denied(store: S3Storage) -> None:
    wrong = get_storage(_settings(store.client._bucket, s3_secret_access_key="wrong-secret"))
    with pytest.raises(StorageUnavailable) as denied:
        await wrong.exists("attachments/x")
    assert denied.value.reason == "s3.denied"
