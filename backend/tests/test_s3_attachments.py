"""Attachments with `HERD_STORAGE=s3` (plan M9 task 14): upload, download, export and
the delayed removal go to the object store, nothing to the local directory, and a store
that does not answer is 503 `storage.unavailable`."""

import io
import zipfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import get_storage
from app.core.storage_s3 import S3Storage
from tests.factories_wiki import Wiki, new_page
from tests.support.s3_stub import S3Stub
from tests.test_wiki_attachments import PNG, _after_the_grace, _error, _upload, _uploaded


def _stored(data_dir: Path) -> list[Path]:
    return [p for p in data_dir.rglob("*") if p.is_file()] if data_dir.exists() else []


async def test_attachments_live_in_the_object_store(
    wiki: Wiki, s3_storage: S3Stub, data_dir: Path, session: AsyncSession
) -> None:
    assert isinstance(get_storage(), S3Storage)
    page = await new_page(wiki.editor, wiki.space_id, "Bilder")
    body = await _uploaded(wiki.editor, page, "logo.png", PNG)
    key = f"attachments/{wiki.users['editor'].org_id}/{body['sha256']}"
    assert list(s3_storage.state.objects) == [key]
    assert s3_storage.state.objects[key].data == PNG
    assert _stored(data_dir) == []

    r = await wiki.editor.get(body["url"])
    assert r.status_code == 200 and r.content == PNG

    export = await wiki.editor.get(f"/api/spaces/{wiki.space_id}/export")
    assert export.status_code == 200, export.text
    names = zipfile.ZipFile(io.BytesIO(export.content)).namelist()
    assert any(name.endswith("logo.png") for name in names)

    assert (await wiki.editor.delete(body["url"])).status_code == 204
    assert key in s3_storage.state.objects  # until the grace has passed
    assert await _after_the_grace(session) == 1
    assert s3_storage.state.objects == {}


async def test_a_failing_store_answers_503(wiki: Wiki, s3_storage: S3Stub) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Bilder")
    body = await _uploaded(wiki.editor, page, "logo.png", PNG)
    s3_storage.state.failures.append(500)
    _error(await wiki.editor.get(body["url"]), 503, "storage.unavailable")
    s3_storage.state.failures.append(503)
    _error(await _upload(wiki.editor, page, "zwei.png", PNG + b"2"), 503, "storage.unavailable")
    listed = (await wiki.editor.get(f"/api/pages/{page['id']}/attachments")).json()
    assert [a["id"] for a in listed["items"]] == [body["id"]]  # the failed upload left no row
