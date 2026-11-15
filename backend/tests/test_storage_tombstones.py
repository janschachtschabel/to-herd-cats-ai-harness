"""Files of deleted attachments stay for a grace period (plan M9 decision 4): deleting
the last attachment of a content writes a tombstone in the same transaction, and the
due loop removes the file 48 hours later, unless the content is in use again. A backup
that took its snapshot before the delete still finds the file."""

from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.core.models_base import utcnow
from app.core.storage_tombstones import GRACE, StorageTombstone
from app.worker.due import DueLoop
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.test_wiki_attachment_commit import PDF, PNG, _files, _page_with


async def _tombstones(real_db: RealDb) -> list[str]:
    async with real_db.database.session_factory() as s:
        return list((await s.scalars(select(StorageTombstone.storage_key))).all())


async def test_deleting_an_attachment_leaves_the_file_for_48_hours(
    real_db: RealDb, make_real_client: MakeRealClient, data_dir: Path
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    _, (attachment,) = await _page_with(owner, ("a.png", PNG))
    assert (await owner.delete(attachment["url"])).status_code == 204
    (stored,) = _files(data_dir)
    assert await _tombstones(real_db) == [stored.relative_to(data_dir).as_posix()]

    clock = SettableClock(utcnow() + GRACE - timedelta(minutes=5))
    loop = DueLoop(real_db.database, clock=clock)
    assert await loop.remove_buried_files() == 0
    assert _files(data_dir) == [stored]

    clock.advance(timedelta(minutes=10))
    assert await loop.remove_buried_files() == 1
    assert _files(data_dir) == []
    assert await _tombstones(real_db) == []


async def test_the_due_loop_removes_a_file_after_the_grace_unless_reused(
    real_db: RealDb, make_real_client: MakeRealClient, data_dir: Path
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    page, (png, pdf) = await _page_with(owner, ("a.png", PNG), ("b.pdf", PDF))
    assert (await owner.delete(png["url"])).status_code == 204
    assert (await owner.delete(pdf["url"])).status_code == 204
    # The same PNG again, before the grace has passed: its file is in use.
    r = await owner.post(
        f"/api/pages/{page['id']}/attachments",
        params={"filename": "again.png"},
        content=PNG,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert r.status_code == 201, r.text
    assert len(await _tombstones(real_db)) == 2

    loop = DueLoop(real_db.database, clock=SettableClock(utcnow() + GRACE + timedelta(hours=1)))
    assert await loop.remove_buried_files() == 1  # the PDF's file
    assert await _tombstones(real_db) == []
    (left,) = _files(data_dir)
    assert (await owner.get(r.json()["url"])).content == PNG
    assert left.read_bytes() == PNG


async def test_deleting_twice_keeps_one_tombstone_with_the_later_time(
    real_db: RealDb, make_real_client: MakeRealClient, data_dir: Path
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    page, (first,) = await _page_with(owner, ("a.png", PNG))
    assert (await owner.delete(first["url"])).status_code == 204
    async with real_db.database.session_factory() as s:
        before = await s.scalar(select(StorageTombstone.buried_at))
    r = await owner.post(
        f"/api/pages/{page['id']}/attachments",
        params={"filename": "b.png"},
        content=PNG,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert (await owner.delete(r.json()["url"])).status_code == 204
    async with real_db.database.session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(StorageTombstone)) == 1
        after = await s.scalar(select(StorageTombstone.buried_at))
    assert before is not None and after is not None and after > before
