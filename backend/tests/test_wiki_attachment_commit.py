"""Attachment files leave the storage only after the deleting transaction committed
and the tombstone's grace has passed (real get_session, tests/real_db.py): a failed
commit keeps row and file together and writes no tombstone."""

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage_tombstones import StorageTombstone
from app.modules.wiki.models import Attachment
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n%..."


def _files(data_dir: Path) -> list[Path]:
    return [p for p in data_dir.rglob("*") if p.is_file()]


async def _rows(real_db: RealDb, table: type = Attachment) -> int:
    async with real_db.database.session_factory() as s:
        return int(await s.scalar(select(func.count()).select_from(table)) or 0)


async def _page_with(owner: AsyncClient, *files: tuple[str, bytes]) -> tuple[Any, list[Any]]:
    space = (await owner.post("/api/spaces", json={"name": "Dateien", "kind": "team"})).json()
    r = await owner.post(f"/api/spaces/{space['id']}/pages", json={"title": "Seite"})
    page = r.json()
    attachments = []
    for name, data in files:
        r = await owner.post(
            f"/api/pages/{page['id']}/attachments",
            params={"filename": name},
            content=data,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert r.status_code == 201, r.text
        attachments.append(r.json())
    return page, attachments


def _fail_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_commit(self: AsyncSession) -> Any:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)


async def test_failed_commit_of_a_delete_keeps_the_file(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    _, (attachment,) = await _page_with(owner, ("a.png", PNG))
    with monkeypatch.context() as patch:  # undo() would also undo `data_dir`
        _fail_commits(patch)
        r = await owner.delete(attachment["url"])
    assert r.status_code == 500
    assert await _rows(real_db) == 1
    assert await _rows(real_db, StorageTombstone) == 0
    assert len(_files(data_dir)) == 1
    r = await owner.get(attachment["url"])
    assert r.content == PNG, r.text
    # Committed, the file is buried (the due loop removes it after the grace).
    assert (await owner.delete(attachment["url"])).status_code == 204
    assert await _rows(real_db) == 0
    assert await _rows(real_db, StorageTombstone) == 1


async def test_failed_commit_of_a_purge_keeps_the_files(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    page, _ = await _page_with(owner, ("a.png", PNG), ("b.pdf", PDF))
    r = await owner.post(f"/api/pages/{page['id']}/trash", json={"version": page["version"]})
    assert r.status_code == 204, r.text
    with monkeypatch.context() as patch:
        _fail_commits(patch)
        r = await owner.delete(f"/api/pages/{page['id']}")
    assert r.status_code == 500
    assert await _rows(real_db) == 2
    assert await _rows(real_db, StorageTombstone) == 0
    assert len(_files(data_dir)) == 2
    assert (await owner.delete(f"/api/pages/{page['id']}")).status_code == 204
    assert await _rows(real_db) == 0
    assert await _rows(real_db, StorageTombstone) == 2


async def test_file_still_used_after_commit_stays(
    real_db: RealDb, make_real_client: MakeRealClient, data_dir: Path
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    _, (first, second) = await _page_with(owner, ("a.png", PNG), ("b.png", PNG))
    assert (await owner.delete(first["url"])).status_code == 204
    assert len(_files(data_dir)) == 1
    assert (await owner.get(second["url"])).content == PNG
