"""The virus scan holds no database connection (review M9b Task 18, R18-6), and skill
imports are scanned too (R18-7).

Tested structurally: every scan records whether the request's session was inside a
transaction when it began. The test session joins its connection with savepoints, so
it keeps that connection; in production a session outside a transaction has returned
its connection to the pool. Outside a transaction at the scan therefore means no
pooled connection waits for clamd. The scan stays fail closed (`test_virus_scan.py`)."""

import io
import zipfile
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import virus_scan
from app.core.config import Settings, get_settings
from app.modules.skills.models import Skill
from tests.factories_wiki import Wiki, new_page
from tests.support.clamd_stub import EICAR, ClamdStub

SKILL_MD = b"---\nname: notizen\ndescription: Notizen schreiben\n---\n\nSchreib kurz.\n"


@pytest.fixture
async def scans(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> AsyncIterator[list[bool]]:
    """Whether the session was in a transaction at each scan, against a real stub."""
    stub = await ClamdStub().start()
    monkeypatch.setattr(get_settings(), "clamav_address", stub.address)
    seen: list[bool] = []
    original = virus_scan.scan

    async def watched(settings: Settings, chunks: AsyncIterator[bytes]) -> None:
        seen.append(session.in_transaction())
        await original(settings, chunks)

    monkeypatch.setattr(virus_scan, "scan", watched)
    yield seen
    await stub.stop()


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _ok(answer: Any, status: int = 200) -> None:
    assert answer.status_code == status, answer.text


async def test_an_upload_is_scanned_outside_any_transaction(wiki: Wiki, scans: list[bool]) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Scan")
    answer = await wiki.editor.post(
        f"/api/pages/{page['id']}/attachments",
        params={"filename": "notiz.txt"},
        content=b"Text\n",
        headers={"Content-Type": "application/octet-stream"},
    )
    _ok(answer, 201)
    assert scans == [False]


async def test_a_wiki_import_is_scanned_outside_any_transaction(
    wiki: Wiki, scans: list[bool]
) -> None:
    answer = await wiki.admin.post(
        f"/api/spaces/{wiki.space_id}/import",
        content=_zip({"seite.md": b"# Seite\n"}),
        headers={"Content-Type": "application/zip"},
    )
    _ok(answer)
    assert scans == [False]


async def test_a_skill_import_is_scanned_outside_any_transaction(
    wiki: Wiki, scans: list[bool]
) -> None:
    answer = await wiki.admin.post(
        "/api/skills/import", content=SKILL_MD, headers={"Content-Type": "text/markdown"}
    )
    _ok(answer)
    assert answer.json()["created"][0]["name"] == "notizen"
    assert scans == [False]


@pytest.mark.parametrize("zipped", [False, True])
async def test_an_infected_skill_import_is_refused(
    wiki: Wiki, scans: list[bool], session: AsyncSession, zipped: bool
) -> None:
    body = _zip({"notizen/SKILL.md": SKILL_MD, "notizen/eicar.txt": EICAR}) if zipped else EICAR
    answer = await wiki.admin.post(
        "/api/skills/import",
        content=body,
        headers={"Content-Type": "application/zip" if zipped else "text/markdown"},
    )
    assert answer.status_code == 422, answer.text
    assert answer.json()["error"]["code"] == "attachment.rejected_by_scan"
    assert await session.scalar(select(func.count()).select_from(Skill)) == 0
