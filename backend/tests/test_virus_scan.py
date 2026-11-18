"""An optional virus scanner (ASVS 5.0 V5.4.3, plan M9 task 18, J11): with
HERD_CLAMAV_ADDRESS set, attachments and imports are scanned by clamd before they are
stored; a find is refused with 422, a scanner that fails, hangs or cannot be reached
refuses with 503 (fail closed). Without it, uploads behave as before."""

import io
import zipfile
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import virus_scan
from app.core.config import get_settings
from app.modules.wiki.models import Attachment
from tests.factories_wiki import Wiki, new_page
from tests.support.clamd_stub import EICAR, ClamdStub

CLEAN = b"Nur ein Text.\n"


@pytest.fixture
async def clamd(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[ClamdStub]:
    stub = await ClamdStub().start()
    monkeypatch.setattr(get_settings(), "clamav_address", stub.address)
    yield stub
    await stub.stop()


async def _upload(client: AsyncClient, page: dict[str, Any], name: str, data: bytes) -> Any:
    return await client.post(
        f"/api/pages/{page['id']}/attachments",
        params={"filename": name},
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )


async def _stored(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(Attachment)) or 0)


def _error(answer: Any, status: int, code: str) -> None:
    assert answer.status_code == status, answer.text
    assert answer.json()["error"]["code"] == code


async def test_an_infected_upload_is_refused(
    wiki: Wiki, clamd: ClamdStub, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Scan")
    assert (await _upload(wiki.editor, page, "notiz.txt", CLEAN)).status_code == 201
    _error(await _upload(wiki.editor, page, "eicar.txt", EICAR), 422, "attachment.rejected_by_scan")
    assert clamd.received == 2
    assert await _stored(session) == 1


async def test_an_infected_import_is_refused(wiki: Wiki, clamd: ClamdStub) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("seite.md", "# Seite\n")
        archive.writestr("seite/eicar.txt", EICAR)
    answer = await wiki.admin.post(
        f"/api/spaces/{wiki.space_id}/import",
        content=buffer.getvalue(),
        headers={"Content-Type": "application/zip"},
    )
    _error(answer, 422, "attachment.rejected_by_scan")
    tree = await wiki.admin.get(f"/api/spaces/{wiki.space_id}/pages/tree")
    assert tree.json()["items"] == []


@pytest.mark.parametrize("mode", ["error", "hang", "close", "unreachable"])
async def test_an_unreachable_scanner_refuses_uploads_when_configured(
    wiki: Wiki,
    clamd: ClamdStub,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Scan")
    monkeypatch.setattr(virus_scan, "SCAN_SECONDS", 0.5)
    clamd.mode = mode
    if mode == "unreachable":
        await clamd.stop()
    _error(await _upload(wiki.editor, page, "notiz.txt", CLEAN), 503, "attachment.scan_unavailable")
    assert await _stored(session) == 0


async def test_no_scanner_configured_keeps_todays_behaviour(
    wiki: Wiki, session: AsyncSession
) -> None:
    assert get_settings().clamav_address == ""
    page = await new_page(wiki.editor, wiki.space_id, "Ohne Scan")
    assert (await _upload(wiki.editor, page, "eicar.txt", EICAR)).status_code == 201
    assert await _stored(session) == 1


@pytest.mark.parametrize("value", ["clamd", "clamd:0", "clamd:70000", "http://clamd:3310", ":3310"])
def test_the_address_must_be_host_and_port(value: str) -> None:
    from app.core.config import Settings

    with pytest.raises(ValueError, match="HERD_CLAMAV_ADDRESS"):
        Settings(clamav_address=value)
