"""Links to attachments survive an export and import: the archive lists which
attachment each `_attachments/` file was (`_attachments/manifest.json`), and the import
points links to those at the new attachments; every other link stays as it was."""

import io
import json
import zipfile
from typing import Any

from httpx import AsyncClient
from uuid_utils.compat import uuid7

from tests.factories_wiki import Wiki, new_page

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MANIFEST = "_attachments/manifest.json"


def _zip(files: dict[str, bytes | str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _unzip(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


async def _import(client: AsyncClient, space_id: object, data: bytes) -> Any:
    r = await client.post(
        f"/api/spaces/{space_id}/import", content=data, headers={"Content-Type": "application/zip"}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _page_at(client: AsyncClient, space_id: object, path: str) -> Any:
    r = await client.get(f"/api/spaces/{space_id}/pages/by-path", params={"path": path})
    assert r.status_code == 200, r.text
    return r.json()


async def _attachment_ids(client: AsyncClient, page_id: str) -> list[str]:
    r = await client.get(f"/api/pages/{page_id}/attachments")
    return [a["id"] for a in r.json()["items"]]


async def test_export_import_points_links_at_the_new_attachments(
    wiki: Wiki, make_space: Any
) -> None:
    page = await new_page(wiki.admin, wiki.space_id, "Bilder")
    r = await wiki.admin.post(
        f"/api/pages/{page['id']}/attachments", params={"filename": "logo.png"}, content=PNG
    )
    old = r.json()["id"]
    foreign = str(uuid7())  # an attachment the archive does not carry
    text = (
        f"![Logo](/api/attachments/{old}?inline=1)\n"
        f"[Datei](/api/attachments/{old}) und [fremd](/api/attachments/{foreign})\n"
        f"https://example.com/api/attachments/{old}\n"
    )
    r = await wiki.admin.patch(
        f"/api/pages/{page['id']}", json={"content_md": text, "version": page["version"]}
    )
    assert r.status_code == 200, r.text
    exported = (await wiki.admin.get(f"/api/spaces/{wiki.space_id}/export")).content
    files = _unzip(exported)
    assert json.loads(files[MANIFEST]) == {"attachments": {"_attachments/bilder/logo.png": old}}

    copy = await make_space("team", "Kopie")
    assert await _import(wiki.admin, copy.id, exported) == {
        "created": 1,
        "attachments": 1,
        "skipped": [],
    }
    copied = await _page_at(wiki.admin, copy.id, "bilder")
    (new,) = await _attachment_ids(wiki.admin, copied["id"])
    assert copied["content_md"] == (
        f"![Logo](/api/attachments/{new}?inline=1)\n"
        f"[Datei](/api/attachments/{new}) und [fremd](/api/attachments/{foreign})\n"
        f"https://example.com/api/attachments/{old}\n"  # another host: not ours to change
    )
    # One version: the rewrite belongs to the import's own first version.
    versions = (await wiki.admin.get(f"/api/pages/{copied['id']}/versions")).json()["items"]
    assert [(v["number"], v["source"]) for v in versions] == [(1, "import")]
    version = (await wiki.admin.get(f"/api/pages/{copied['id']}/versions/1")).json()
    assert version["content_md"] == copied["content_md"]


async def test_links_to_refused_or_unlisted_attachments_stay(wiki: Wiki) -> None:
    refused, unlisted = str(uuid7()), str(uuid7())
    body = f"[a](/api/attachments/{refused}) [b](/api/attachments/{unlisted})\n"
    archive = _zip(
        {
            "seite.md": body,
            "_attachments/seite/bild.png": b"<html>not a png</html>",
            "_attachments/seite/ok.png": PNG,
            MANIFEST: json.dumps({"attachments": {"_attachments/seite/bild.png": refused}}),
        }
    )
    result = await _import(wiki.admin, wiki.space_id, archive)
    assert result["attachments"] == 1
    assert [s["path"] for s in result["skipped"]] == ["_attachments/seite/bild.png"]
    page = await _page_at(wiki.admin, wiki.space_id, "seite")
    assert page["content_md"] == body


async def test_a_broken_manifest_is_skipped_and_nothing_is_rewritten(wiki: Wiki) -> None:
    old = str(uuid7())
    body = f"[a](/api/attachments/{old})\n"
    for manifest in ("{not json", json.dumps({"attachments": {"x": "no-uuid"}}), "[]"):
        space = f"s{len(manifest)}"
        archive = _zip(
            {
                f"{space}.md": body,
                f"_attachments/{space}/ok.png": PNG,
                MANIFEST: manifest,
            }
        )
        result = await _import(wiki.admin, wiki.space_id, archive)
        assert result["skipped"] == [{"path": MANIFEST, "reason": "invalid_manifest"}]
        assert result["attachments"] == 1
        page = await _page_at(wiki.admin, wiki.space_id, space)
        assert page["content_md"] == body


async def test_export_without_attachments_has_no_manifest(wiki: Wiki) -> None:
    await new_page(wiki.admin, wiki.space_id, "Leer", content_md="Text")
    files = _unzip((await wiki.admin.get(f"/api/spaces/{wiki.space_id}/export")).content)
    assert set(files) == {"leer.md"}
