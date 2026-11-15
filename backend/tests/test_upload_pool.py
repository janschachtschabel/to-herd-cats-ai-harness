"""Uploads and imports hold no database connection while their body arrives (review M2
R4), and a body that stops arriving is answered 408 (pool of one connection).

The rights are checked in a short transaction that ends before the body is read; the
work after the body opens a new one and checks the rights again.
"""

import asyncio
import io
import time
import zipfile
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import Database, set_database
from app.modules.wiki.models import Attachment
from app.modules.wiki.transfer import PageImport
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

FAST_ENOUGH = 1.0  # a request that waited for the pooled connection takes 10 s


@pytest.fixture
async def one_connection(real_db: RealDb) -> AsyncIterator[Database]:
    database = Database(
        get_settings().test_database_url, pool_size=1, max_overflow=0, pool_timeout=10
    )
    set_database(database)
    try:
        yield database
    finally:
        set_database(real_db.database)
        await database.dispose()


async def _stalled(release: asyncio.Event, data: bytes) -> AsyncIterator[bytes]:
    """Two bytes, then nothing until `release`, then the rest."""
    yield data[:2]
    await release.wait()
    yield data[2:]


def _zip(files: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in (files or {"Neu.md": b"# Neu\n"}).items():
            archive.writestr(name, data)
    return buffer.getvalue()


async def _space_and_page(owner: AsyncClient) -> tuple[str, str]:
    space = (await owner.post("/api/spaces", json={"name": "Dateien", "kind": "team"})).json()
    page = (await owner.post(f"/api/spaces/{space['id']}/pages", json={"title": "Seite"})).json()
    return space["id"], page["id"]


async def _served_quickly(client: AsyncClient) -> None:
    started = time.perf_counter()
    me = await client.get("/api/auth/me")
    took = time.perf_counter() - started
    assert me.status_code == 200 and took < FAST_ENOUGH, took


async def test_stalled_uploads_and_imports_hold_no_connection(
    real_db: RealDb, make_real_client: MakeRealClient, one_connection: Database
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space_id, page_id = await _space_and_page(owner)
    release = asyncio.Event()
    octets = {"Content-Type": "application/octet-stream"}
    upload = asyncio.create_task(
        owner.post(
            f"/api/pages/{page_id}/attachments",
            params={"filename": "notiz.txt"},
            content=_stalled(release, b"eine Notiz"),
            headers=octets,
        )
    )
    imported = asyncio.create_task(
        owner.post(
            f"/api/spaces/{space_id}/import",
            content=_stalled(release, _zip()),
            headers={"Content-Type": "application/zip"},
        )
    )
    try:
        await asyncio.sleep(0.3)  # both bodies have started and stalled
        await _served_quickly(owner)
    finally:
        release.set()  # a failing test must not leave transactions open
        uploaded, done = await asyncio.gather(upload, imported)
    assert uploaded.status_code == 201, uploaded.text
    assert done.status_code == 200 and done.json()["created"] == 1, done.text


async def test_an_import_with_attachments_stays_one_transaction(
    real_db: RealDb, make_real_client: MakeRealClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the route's own wait for the body ends a transaction: the attachments an
    import stores are part of it, so a failure afterwards leaves nothing behind."""
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space_id, _ = await _space_and_page(owner)

    async def failing_relink(self: PageImport) -> None:
        raise RuntimeError("late failure")

    monkeypatch.setattr(PageImport, "_relink", failing_relink)
    data = _zip({"Neu.md": b"# Neu\n", "_attachments/Neu/notiz.txt": b"eine Notiz"})
    response = await owner.post(f"/api/spaces/{space_id}/import", content=data)
    assert response.status_code == 500
    tree = (await owner.get(f"/api/spaces/{space_id}/pages/tree")).json()["items"]
    assert [node["title"] for node in tree] == ["Seite"]
    async with real_db.database.session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(Attachment)) == 0


async def test_rights_lost_while_the_body_arrives_are_checked_again(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space_id, page_id = await _space_and_page(owner)
    release = asyncio.Event()
    upload = asyncio.create_task(
        owner.post(
            f"/api/pages/{page_id}/attachments",
            params={"filename": "notiz.txt"},
            content=_stalled(release, b"eine Notiz"),
            headers={"Content-Type": "application/octet-stream"},
        )
    )
    try:
        await asyncio.sleep(0.3)
        trashed = await owner.post(f"/api/pages/{page_id}/trash", json={"version": 1})
        assert trashed.status_code == 204
    finally:
        release.set()
    assert (await upload).status_code == 404
    assert (await owner.get(f"/api/pages/{page_id}/attachments")).status_code == 404
    del space_id


async def test_a_body_that_stops_arriving_is_answered_408(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    one_connection: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "body_read_timeout_seconds", 0.3)
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space_id, page_id = await _space_and_page(owner)
    never = asyncio.Event()
    for url, data in (
        (f"/api/pages/{page_id}/attachments?filename=a.txt", b"abc"),
        (f"/api/spaces/{space_id}/import", _zip()),
    ):
        response = await owner.post(url, content=_stalled(never, data))
        assert response.status_code == 408, response.text
        error = response.json()["error"]
        assert error["code"] == "request.timeout"
        assert len(error["trace_id"]) == 32
    await _served_quickly(owner)
