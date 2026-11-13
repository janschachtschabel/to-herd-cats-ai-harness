"""Attachments: upload (type by content, size limit), list, download with safe headers,
delete, and what happens with the page (plan M2 task 6)."""

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.config import Settings, get_settings
from app.modules.audit.models import AuditLog
from app.modules.wiki.models import Attachment
from tests.factories_wiki import Wiki, new_page, publish

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PDF = b"%PDF-1.7\n%..."


def _zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


async def _upload(
    client: AsyncClient, page: dict[str, Any], filename: str, data: bytes, **headers: str
) -> Any:
    return await client.post(
        f"/api/pages/{page['id']}/attachments",
        params={"filename": filename},
        content=data,
        headers={"Content-Type": "application/octet-stream", **headers},
    )


async def _uploaded(client: AsyncClient, page: dict[str, Any], name: str, data: bytes) -> Any:
    r = await _upload(client, page, name, data)
    assert r.status_code == 201, r.text
    return r.json()


def _error(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code


def _stored_files(data_dir: Path) -> list[Path]:
    return [p for p in data_dir.rglob("*") if p.is_file()]


async def test_upload_and_download_roundtrip(wiki: Wiki, data_dir: Path) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Bilder")
    body = await _uploaded(wiki.editor, page, "logo.png", PNG)
    assert {k: body[k] for k in ("page_id", "filename", "mime", "size")} == {
        "page_id": page["id"],
        "filename": "logo.png",
        "mime": "image/png",
        "size": len(PNG),
    }
    assert body["url"] == f"/api/attachments/{body['id']}"
    assert body["uploaded_by"] == {"type": "user", "id": str(wiki.users["editor"].id)}
    listed = (await wiki.editor.get(f"/api/pages/{page['id']}/attachments")).json()
    assert [a["id"] for a in listed["items"]] == [body["id"]]

    r = await wiki.editor.get(body["url"])
    assert r.status_code == 200 and r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["content-length"] == str(len(PNG))
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-disposition"].startswith("attachment;")
    assert "sandbox" in r.headers["content-security-policy"]
    inline = await wiki.editor.get(body["url"], params={"inline": 1})
    assert inline.headers["content-disposition"].startswith("inline;")
    stored = _stored_files(data_dir)
    org_id = str(wiki.users["editor"].org_id)
    assert [p.relative_to(data_dir).as_posix() for p in stored] == [
        f"attachments/{org_id}/{body['sha256']}"
    ]


async def test_only_raster_images_are_shown_inline(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Dateien")
    pdf = await _uploaded(wiki.editor, page, "plan.pdf", PDF)
    note = await _uploaded(wiki.editor, page, "notiz.txt", b"Hallo")
    for attachment in (pdf, note):
        r = await wiki.editor.get(attachment["url"], params={"inline": 1})
        assert r.headers["content-disposition"].startswith("attachment;")
    r = await wiki.editor.get(note["url"])
    assert r.headers["content-type"] == "text/plain; charset=utf-8"


@pytest.mark.parametrize(
    ("name", "data", "mime"),
    [
        ("foto.jpg", JPEG, "image/jpeg"),
        ("foto.JPEG", JPEG, "image/jpeg"),
        ("anim.gif", b"GIF89a" + b"\x00" * 10, "image/gif"),
        ("bild.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
        ("plan.pdf", PDF, "application/pdf"),
        ("liste.csv", b"a;b\n1;2\n", "text/csv"),
        ("notiz.md", "# Überschrift\n".encode(), "text/markdown"),
        ("daten.json", b'{"a": [1, 2]}', "application/json"),
        ("paket.zip", _zip({"a.txt": b"x"}), "application/zip"),
        (
            "brief.docx",
            _zip({"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<w/>"}),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "tabelle.xlsx",
            _zip({"[Content_Types].xml": b"<Types/>", "xl/workbook.xml": b"<x/>"}),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "folien.pptx",
            _zip({"[Content_Types].xml": b"<Types/>", "ppt/presentation.xml": b"<p/>"}),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    ],
)
async def test_allowed_types_are_recognised_by_content(
    wiki: Wiki, name: str, data: bytes, mime: str
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Dateien")
    assert (await _uploaded(wiki.editor, page, name, data))["mime"] == mime


async def test_html_disguised_as_png_is_rejected(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Bilder")
    for data in (
        b"<html><script>alert(1)</script></html>",
        b"  \n<!DOCTYPE html><p>x</p>",
        b"\xef\xbb\xbf<HTML>",
        b"Some text first\n<script>alert(1)</script>",
    ):
        r = await _upload(wiki.editor, page, "bild.png", data, **{"Content-Type": "image/png"})
        _error(r, 415, "attachment.type_not_allowed")
    # The same holds for text names.
    _error(
        await _upload(wiki.editor, page, "notiz.txt", b"<html>"), 415, "attachment.type_not_allowed"
    )


async def test_svg_is_rejected(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Bilder")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    for name, data in (
        ("logo.svg", svg),
        ("logo.png", svg),
        ("logo.txt", b'<?xml version="1.0"?>\n' + svg),
    ):
        _error(await _upload(wiki.editor, page, name, data), 415, "attachment.type_not_allowed")


async def test_content_and_name_must_agree(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Bilder")
    for name, data in (
        ("seite.html", PNG),  # a PNG named like a page
        ("bild.jpg", PNG),
        ("ohne-endung", PNG),
        ("skript.js", b"alert(1)"),
        ("notiz.md.exe", b"text"),
        ("bericht.docx", _zip({"a.txt": b"x"})),  # a plain ZIP is no DOCX
    ):
        _error(await _upload(wiki.editor, page, name, data), 415, "attachment.type_mismatch")
    for name, data in (
        ("run.exe", b"MZ\x90\x00"),
        ("kaputt.zip", b"PK\x03\x04 not really a zip"),
        ("daten.json", b"{not json"),
        ("leer.txt", b"\x00\x01\x02"),
    ):
        _error(await _upload(wiki.editor, page, name, data), 415, "attachment.type_not_allowed")


async def test_size_limit_is_a_route_specific_body_limit(wiki: Wiki, monkeypatch) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Gross")
    # Above the global request limit (1 MiB), below the attachment limit (25 MiB).
    big = b"a" * (2 * 1024 * 1024)
    assert (await _uploaded(wiki.editor, page, "gross.txt", big))["size"] == len(big)
    # Elsewhere the global limit still holds.
    r = await wiki.editor.patch(
        f"/api/pages/{page['id']}", content=big, headers={"Content-Type": "application/json"}
    )
    _error(r, 413, "request.too_large")


async def test_streamed_upload_is_cut_off_at_the_attachment_limit(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Gross")
    chunk = b"a" * (1024 * 1024)

    async def streamed() -> Any:
        for _ in range(26):
            yield chunk

    r = await wiki.editor.post(
        f"/api/pages/{page['id']}/attachments", params={"filename": "x.txt"}, content=streamed()
    )
    _error(r, 413, "request.too_large")
    assert (await wiki.editor.get(f"/api/pages/{page['id']}/attachments")).json()["items"] == []


async def test_upload_over_the_limit_is_413(wiki: Wiki, monkeypatch) -> None:
    assert Settings().attachment_max_bytes == 25 * 1024 * 1024
    page = await new_page(wiki.editor, wiki.space_id, "Gross")
    # The service holds the limit too (here the app's body limit was set before).
    monkeypatch.setattr(get_settings(), "attachment_max_bytes", 1024)
    r = await _upload(wiki.editor, page, "x.txt", b"a" * 1025)
    _error(r, 413, "attachment.too_large")
    assert (await _uploaded(wiki.editor, page, "x.txt", b"a" * 1024))["size"] == 1024


async def test_same_content_is_stored_once(wiki: Wiki, data_dir: Path) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Bilder")
    first = await _uploaded(wiki.editor, page, "a.png", PNG)
    second = await _uploaded(wiki.editor, page, "b.png", PNG)
    assert first["id"] != second["id"] and first["sha256"] == second["sha256"]
    assert len(_stored_files(data_dir)) == 1
    # The file stays while another attachment uses it, and goes with the last one.
    assert (await wiki.editor.delete(first["url"])).status_code == 204
    assert len(_stored_files(data_dir)) == 1
    assert (await wiki.editor.get(second["url"])).content == PNG
    assert (await wiki.editor.delete(second["url"])).status_code == 204
    assert _stored_files(data_dir) == []
    _error(await wiki.editor.get(second["url"]), 404, "attachment.not_found")


async def test_attachment_permissions_follow_the_page(wiki: Wiki) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Bilder"))
    attachment = await _uploaded(wiki.editor, page, "a.png", PNG)
    assert (await wiki.viewer.get(attachment["url"])).status_code == 200
    _error(await _upload(wiki.viewer, page, "b.png", PNG), 403, "auth.permission_denied")
    _error(await wiki.viewer.delete(attachment["url"]), 403, "auth.permission_denied")
    assert (await wiki.viewer.get(f"/api/pages/{page['id']}/attachments")).status_code == 200


async def test_download_of_attachment_in_invisible_space_is_404(
    wiki: Wiki, guest_client: AsyncClient
) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Geheim"))
    attachment = await _uploaded(wiki.editor, page, "a.png", PNG)
    for client in (wiki.outsider, guest_client):
        for r in (
            await client.get(attachment["url"]),
            await client.delete(attachment["url"]),
            await client.get(f"/api/attachments/{uuid7()}"),
        ):
            _error(r, 404, "attachment.not_found")
        for r in (
            await client.get(f"/api/pages/{page['id']}/attachments"),
            await _upload(client, page, "b.png", PNG),
        ):
            _error(r, 404, "page.not_found")


async def test_attachments_of_drafts_and_trashed_pages_are_hidden(wiki: Wiki) -> None:
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    on_draft = await _uploaded(wiki.editor, draft, "a.png", PNG)
    _error(await wiki.viewer.get(on_draft["url"]), 404, "attachment.not_found")
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Weg"))
    attachment = await _uploaded(wiki.editor, page, "b.png", PNG)
    r = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": page["version"]}
    )
    assert r.status_code == 204
    for client in (wiki.viewer, wiki.moderator):
        _error(await client.get(attachment["url"]), 404, "attachment.not_found")
    _error(await _upload(wiki.editor, page, "c.png", PNG), 404, "page.not_found")
    # Back from the trash, back in reach.
    assert (await wiki.moderator.post(f"/api/pages/{page['id']}/restore")).status_code == 200
    assert (await wiki.viewer.get(attachment["url"])).status_code == 200


async def test_purge_deletes_attachments_and_unused_files(
    wiki: Wiki, session: AsyncSession, data_dir: Path
) -> None:
    keep = await new_page(wiki.editor, wiki.space_id, "Bleibt")
    await _uploaded(wiki.editor, keep, "shared.png", PNG)
    page = await new_page(wiki.editor, wiki.space_id, "Weg")
    child = await new_page(wiki.editor, wiki.space_id, "Kind", parent_id=page["id"])
    await _uploaded(wiki.editor, page, "shared.png", PNG)
    await _uploaded(wiki.editor, child, "only.pdf", PDF)
    assert len(_stored_files(data_dir)) == 2
    fresh = (await wiki.editor.get(f"/api/pages/{page['id']}")).json()
    r = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": fresh["version"]}
    )
    assert r.status_code == 204
    assert (await wiki.admin.delete(f"/api/pages/{page['id']}")).status_code == 204
    assert await session.scalar(select(func.count()).select_from(Attachment)) == 1
    names = sorted(p.name for p in _stored_files(data_dir))
    assert len(names) == 1  # the PDF is gone, the shared PNG stays for "Bleibt"


async def test_filename_with_quotes_and_newlines_is_safe_in_header(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Namen")
    name = 'a"b\r\nSet-Cookie: x=1;\\ übel/../c.txt'
    attachment = await _uploaded(wiki.editor, page, name, b"Hallo")
    assert attachment["filename"] == 'a"b  Set-Cookie: x=1;_ übel_.._c.txt'
    r = await wiki.editor.get(attachment["url"])
    disposition = r.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    assert "set-cookie" not in {k.lower() for k in r.headers}
    plain, _, encoded = disposition.partition("; filename*=UTF-8''")
    assert plain == 'attachment; filename="a_b  Set-Cookie_ x_1__ _bel_.._c.txt"'
    assert encoded == "a%22b%20%20Set-Cookie%3A%20x%3D1%3B_%20%C3%BCbel_.._c.txt"


async def test_bad_filenames_are_refused(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Namen")
    for name in ("", "   ", "x" * 256 + ".txt"):
        r = await _upload(wiki.editor, page, name, b"Hallo")
        assert r.status_code == 422, (name, r.text)


async def test_attachment_list_is_paginated(wiki: Wiki) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Viele")
    ids = [
        (await _uploaded(wiki.editor, page, f"{i}.txt", str(i).encode()))["id"] for i in range(3)
    ]
    path = f"/api/pages/{page['id']}/attachments"
    first = (await wiki.editor.get(path, params={"limit": 2})).json()
    rest = (await wiki.editor.get(path, params={"limit": 2, "cursor": first["next_cursor"]})).json()
    assert [a["id"] for a in first["items"] + rest["items"]] == ids
    assert rest["next_cursor"] is None


async def test_uploads_and_deletes_are_audited(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Prüfbar")
    attachment = await _uploaded(wiki.editor, page, "a.png", PNG)
    await wiki.editor.delete(attachment["url"])
    rows = (
        await session.scalars(
            select(AuditLog).where(AuditLog.action.like("attachment.%")).order_by(AuditLog.id)
        )
    ).all()
    assert [(r.action, r.details) for r in rows] == [
        ("attachment.uploaded", {"page_id": page["id"], "filename": "a.png", "size": len(PNG)}),
        ("attachment.deleted", {"page_id": page["id"], "filename": "a.png"}),
    ]
    assert json.dumps([r.details for r in rows])  # serialisable
