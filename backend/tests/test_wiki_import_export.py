"""Markdown import and export (plan M2 task 7): a space is a ZIP of `.md` files, one per
page in the path of the tree, with front matter; attachments under `_attachments/`."""

import io
import stat
import struct
import zipfile
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.wiki import archive as archive_module
from tests.factories_wiki import Wiki, new_page, publish

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _zip(files: dict[str, bytes | str], *, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _unzip(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


FIXTURE: dict[str, bytes | str] = {
    "handbuch.md": '---\ntitle: Handbuch\ntags: [start, "intern, vertraulich"]\n---\n# Willkommen\n\nText.\n',
    "handbuch/onboarding.md": "# Onboarding\n\nErste Woche.\n",
    "handbuch/onboarding/checkliste.md": "Punkt 1\n",
    "it/zugaenge.md": "---\ntitle: Zugänge\n---\nVPN und Mail.\n",
    "werkzeuge/index.md": "---\ntitle: Werkzeuge\nstatus: draft\n---\nListe.\n",
}


async def _import(client: AsyncClient, space_id: object, data: bytes) -> Any:
    return await client.post(
        f"/api/spaces/{space_id}/import",
        content=data,
        headers={"Content-Type": "application/zip"},
    )


async def _tree(client: AsyncClient, space_id: object) -> dict[str, dict[str, Any]]:
    r = await client.get(f"/api/spaces/{space_id}/pages/tree", params={"limit": 100})
    assert r.status_code == 200, r.text
    return {n["path"]: n for n in r.json()["items"]}


async def _tag_names(client: AsyncClient, ids: list[str]) -> list[str]:
    tags = (await client.get("/api/tags", params={"limit": 100})).json()["items"]
    return sorted(t["name"] for t in tags if t["id"] in ids)


def _error(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code


async def test_import_builds_tree_from_folders_and_front_matter(wiki: Wiki) -> None:
    r = await _import(wiki.admin, wiki.space_id, _zip(FIXTURE))
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 6, "attachments": 0, "skipped": []}  # + implicit "it"
    tree = await _tree(wiki.admin, wiki.space_id)
    assert set(tree) == {
        "handbuch",
        "handbuch/onboarding",
        "handbuch/onboarding/checkliste",
        "it",
        "it/zugaenge",
        "werkzeuge",
    }
    titles = {path: node["title"] for path, node in tree.items()}
    assert titles == {
        "handbuch": "Handbuch",
        "handbuch/onboarding": "Onboarding",  # from the first heading
        "handbuch/onboarding/checkliste": "Checkliste",  # from the file name
        "it": "It",  # a folder without index.md: an empty page
        "it/zugaenge": "Zugänge",
        "werkzeuge": "Werkzeuge",  # from werkzeuge/index.md
    }
    status = {path: node["status"] for path, node in tree.items()}
    assert status.pop("werkzeuge") == "draft"
    assert set(status.values()) == {"published"}
    page = (await wiki.admin.get(f"/api/pages/{tree['handbuch']['id']}")).json()
    assert page["content_md"] == "# Willkommen\n\nText.\n"
    assert await _tag_names(wiki.admin, page["tags"]) == ["intern, vertraulich", "start"]
    versions = (await wiki.admin.get(f"/api/pages/{page['id']}/versions")).json()["items"]
    assert [v["source"] for v in versions] == ["import"]


async def test_import_skips_existing_paths_and_reports_why(wiki: Wiki) -> None:
    await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Handbuch"))
    files: dict[str, bytes | str] = {
        "handbuch.md": "neu",
        "handbuch/kind.md": "unter dem vorhandenen",
        "bild.png": PNG,
        "nicht-utf8.md": b"\xff\xfe",
        "doppelt.md": "a",
        "Doppelt.md": "b",
        "__MACOSX/._handbuch.md": "ignored",
        "ordner/": "",
    }
    r = await _import(wiki.admin, wiki.space_id, _zip(files))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2  # handbuch/kind, doppelt
    assert sorted((s["path"], s["reason"]) for s in body["skipped"]) == [
        ("Doppelt.md", "duplicate"),
        ("bild.png", "not_markdown"),
        ("handbuch.md", "exists"),
        ("nicht-utf8.md", "invalid_text"),
    ]
    assert "handbuch/kind" in await _tree(wiki.admin, wiki.space_id)


async def test_import_needs_space_manage(wiki: Wiki) -> None:
    for client in (wiki.editor, wiki.moderator):
        _error(await _import(client, wiki.space_id, _zip(FIXTURE)), 403, "auth.permission_denied")
    _error(await _import(wiki.outsider, wiki.space_id, _zip(FIXTURE)), 404, "space.not_found")


async def test_import_rejects_what_is_no_zip(wiki: Wiki) -> None:
    for data in (b"not a zip", b"", b"PK\x05\x06" + b"\x00" * 10):
        _error(await _import(wiki.admin, wiki.space_id, data), 422, "import.invalid_zip")


async def test_zip_slip_entries_are_skipped(wiki: Wiki) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in ("../boese.md", "a/../../boese.md", "/etc/boese.md", "C:/boese.md", "..\\x.md"):
            archive.writestr(name, "x")
        link = zipfile.ZipInfo("link.md")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "/etc/passwd")
        archive.writestr("gut.md", "ok")
    r = await _import(wiki.admin, wiki.space_id, buffer.getvalue())
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1
    reasons = {s["path"]: s["reason"] for s in r.json()["skipped"]}
    assert reasons == {
        "../boese.md": "unsafe_path",
        "a/../../boese.md": "unsafe_path",
        "/etc/boese.md": "unsafe_path",
        "C:/boese.md": "unsafe_path",
        "..\\x.md": "unsafe_path",
        "link.md": "unsafe_path",
    }
    assert set(await _tree(wiki.admin, wiki.space_id)) == {"gut"}


async def test_zip_bomb_is_rejected(wiki: Wiki, monkeypatch) -> None:
    monkeypatch.setattr(archive_module, "MAX_UNPACKED_BYTES", 1024 * 1024)
    bomb = _zip({"bombe.md": b"0" * (2 * 1024 * 1024)})
    assert len(bomb) < 10_000
    _error(await _import(wiki.admin, wiki.space_id, bomb), 413, "import.too_large")
    assert await _tree(wiki.admin, wiki.space_id) == {}


async def test_an_entry_that_lies_about_its_size_is_not_unpacked(wiki: Wiki) -> None:
    data = bytearray(_zip({"luege.md": b"0" * 100_000, "gut.md": "ok"}))
    # Declare 10 bytes for the first entry (local header and central directory).
    for signature, offset in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
        at = data.find(signature)
        data[at + offset : at + offset + 4] = struct.pack("<I", 10)
    r = await _import(wiki.admin, wiki.space_id, bytes(data))
    assert r.status_code == 200, r.text
    assert r.json()["skipped"] == [{"path": "luege.md", "reason": "unreadable"}]
    assert set(await _tree(wiki.admin, wiki.space_id)) == {"gut"}


async def test_too_many_entries_are_refused_before_reading_them(wiki: Wiki, monkeypatch) -> None:
    monkeypatch.setattr(archive_module, "MAX_ENTRIES", 3)
    data = _zip({f"{i}.md": "x" for i in range(4)}, compression=zipfile.ZIP_STORED)

    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("the directory was parsed")

    monkeypatch.setattr(archive_module.zipfile, "ZipFile", explode)
    _error(await _import(wiki.admin, wiki.space_id, data), 413, "import.too_large")


async def test_import_body_has_its_own_limit(wiki: Wiki) -> None:
    from app.core.config import Settings
    from app.web.public import body_limits

    assert Settings().import_max_bytes == 100 * 1024 * 1024
    limits = {r.path.pattern: r.max_bytes for r in body_limits(Settings(import_max_bytes=7))}
    assert limits[r"/api/spaces/[^/]+/import"] == 7
    # Bigger than the global 1 MiB request limit, still accepted.
    big = _zip({"gross.md": "x " * 600_000}, compression=zipfile.ZIP_STORED)
    assert len(big) > 1024 * 1024
    r = await _import(wiki.admin, wiki.space_id, big)
    assert r.status_code == 200 and r.json()["skipped"] == [
        {"path": "gross.md", "reason": "too_large"}
    ]


async def test_published_pages_only_below_published_parents(wiki: Wiki) -> None:
    files: dict[str, bytes | str] = {
        "entwurf.md": "---\nstatus: draft\n---\n",
        "entwurf/kind.md": "veröffentlicht gewünscht",
    }
    assert (await _import(wiki.admin, wiki.space_id, _zip(files))).status_code == 200
    tree = await _tree(wiki.admin, wiki.space_id)
    assert tree["entwurf"]["status"] == tree["entwurf/kind"]["status"] == "draft"


async def test_export_round_trips_content_and_front_matter(wiki: Wiki) -> None:
    await _import(wiki.admin, wiki.space_id, _zip(FIXTURE))
    r = await wiki.admin.get(f"/api/spaces/{wiki.space_id}/export")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert r.headers["content-disposition"].startswith('attachment; filename="wiki.zip"')
    files = _unzip(r.content)
    assert set(files) == {
        "handbuch.md",
        "handbuch/onboarding.md",
        "handbuch/onboarding/checkliste.md",
        "it.md",
        "it/zugaenge.md",
        "werkzeuge.md",
    }
    assert files["handbuch.md"].decode() == (
        '---\ntitle: "Handbuch"\nstatus: "published"\ntags: ["intern, vertraulich", "start"]\n---\n'
        "# Willkommen\n\nText.\n"
    )
    assert files["werkzeuge.md"].decode().startswith('---\ntitle: "Werkzeuge"\nstatus: "draft"\n')


async def test_export_then_import_round_trips_tree_and_tags(
    wiki: Wiki, make_space, session: AsyncSession
) -> None:
    system = (await wiki.admin.post("/api/tags", json={"name": "Systemweit"})).json()
    space_tag = (
        await wiki.admin.post("/api/tags", json={"name": "Nur hier", "space_id": wiki.space_id})
    ).json()
    await _import(wiki.admin, wiki.space_id, _zip(FIXTURE))
    tree = await _tree(wiki.admin, wiki.space_id)
    page = (await wiki.admin.get(f"/api/pages/{tree['it/zugaenge']['id']}")).json()
    r = await wiki.admin.put(
        f"/api/pages/{page['id']}/tags",
        json={"tag_ids": [system["id"], space_tag["id"]], "version": page["version"]},
    )
    assert r.status_code == 200
    r = await wiki.admin.post(
        f"/api/pages/{page['id']}/attachments", params={"filename": "logo.png"}, content=PNG
    )
    assert r.status_code == 201, r.text
    exported = (await wiki.admin.get(f"/api/spaces/{wiki.space_id}/export")).content
    assert _unzip(exported)["_attachments/it/zugaenge/logo.png"] == PNG

    copy = await make_space("team", "Kopie")
    r = await _import(wiki.admin, copy.id, exported)
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 6, "attachments": 1, "skipped": []}
    again = await _tree(wiki.admin, copy.id)
    assert {p: (n["title"], n["status"]) for p, n in again.items()} == {
        p: (n["title"], n["status"]) for p, n in tree.items()
    }
    copied = (await wiki.admin.get(f"/api/pages/{again['it/zugaenge']['id']}")).json()
    assert copied["content_md"] == page["content_md"]
    # The system tag is the same tag; the other space's tag is made anew in the copy.
    assert system["id"] in copied["tags"]
    assert await _tag_names(wiki.admin, copied["tags"]) == ["Nur hier", "Systemweit"]
    assert space_tag["id"] not in copied["tags"]
    files = (await wiki.admin.get(f"/api/pages/{copied['id']}/attachments")).json()["items"]
    assert [(a["filename"], a["mime"]) for a in files] == [("logo.png", "image/png")]
    # And exporting the copy gives the same archive.
    assert _unzip((await wiki.admin.get(f"/api/spaces/{copy.id}/export")).content) == _unzip(
        exported
    )
    actions = (await session.scalars(select(AuditLog.action))).all()
    assert "space.imported" in actions


async def test_export_only_includes_visible_pages(wiki: Wiki) -> None:
    done = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Offen", content_md="a")
    )
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf", content_md="b")
    for page in (done, draft):
        r = await wiki.editor.post(
            f"/api/pages/{page['id']}/attachments", params={"filename": "a.png"}, content=PNG
        )
        assert r.status_code == 201
    viewer = _unzip((await wiki.viewer.get(f"/api/spaces/{wiki.space_id}/export")).content)
    assert set(viewer) == {"offen.md", "_attachments/offen/a.png"}
    editor = _unzip((await wiki.editor.get(f"/api/spaces/{wiki.space_id}/export")).content)
    assert set(editor) == {
        "offen.md",
        "entwurf.md",
        "_attachments/offen/a.png",
        "_attachments/entwurf/a.png",
    }
    r = await wiki.outsider.get(f"/api/spaces/{wiki.space_id}/export")
    _error(r, 404, "space.not_found")


async def test_single_page_export(wiki: Wiki) -> None:
    page = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Über uns", content_md="Hallo")
    )
    r = await wiki.viewer.get(f"/api/pages/{page['id']}/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/markdown; charset=utf-8"
    assert r.headers["content-disposition"].startswith('attachment; filename="ueber-uns.md"')
    assert r.text == '---\ntitle: "Über uns"\nstatus: "published"\ntags: []\n---\nHallo'
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf")
    _error(await wiki.viewer.get(f"/api/pages/{draft['id']}/export"), 404, "page.not_found")


@pytest.mark.parametrize(
    ("text", "meta", "body"),
    [
        ("kein front matter", {}, "kein front matter"),
        ("---\ntitle: A\n---\nB", {"title": "A"}, "B"),
        (
            "---\r\ntitle: \"A: b\"\r\ntags: [x, 'y']\r\n---\r\nB",
            {"title": "A: b", "tags": ["x", "y"]},
            "B",
        ),
        ("---\ntitle: A\nnie geschlossen", {}, "---\ntitle: A\nnie geschlossen"),
        ("---\nnested:\n  a: 1\ntitle: T\n---\n", {"nested": "", "title": "T"}, ""),
    ],
)
def test_front_matter_parsing(text: str, meta: dict[str, Any], body: str) -> None:
    from app.modules.wiki import frontmatter

    assert frontmatter.parse(text) == (meta, body)


def test_front_matter_round_trips_awkward_values() -> None:
    from app.modules.wiki import frontmatter

    meta: frontmatter.Meta = {"title": 'Er sagte: "Hallo", dann ---', "tags": ["a, b", "[c]", "ü"]}
    assert frontmatter.parse(frontmatter.serialise(meta, "---\nText")) == (meta, "---\nText")
