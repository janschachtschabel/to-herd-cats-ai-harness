"""Importing and exporting skills (plan M6 decision 11): a skill leaves as its SKILL.md;
a SKILL.md or a ZIP of skill folders comes in, read as strictly as the wiki import
reads its archives. Every skill reports what became of it; skills carry only their
SKILL.md (no other file is taken, nothing is ever executed)."""

import io
import zipfile
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.skills import transfer
from tests.factories_skills import SKILLS, Lab, listed, made

IMPORT = f"{SKILLS}/import"


def skill_md(name: str, description: str = "Does things.", body: str = "Steps.\n") -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n{body}"


def zipped(files: dict[str, str | bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return buffer.getvalue()


async def _import(client: Any, body: bytes | str, **params: Any) -> Any:
    data = body.encode() if isinstance(body, str) else body
    return await client.post(IMPORT, content=data, params=params)


async def test_a_skill_is_exported_as_its_skill_md_and_imported_again(lab: Lab) -> None:
    skill = await made(
        lab.admin, description="Colons: 'quotes' and #", content="# PDF\n\n---\nnot meta\n"
    )
    response = await lab.alice.get(f"{SKILLS}/{skill['id']}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    assert 'filename="SKILL.md"' in response.headers["content-disposition"]
    assert response.text.startswith("---\nname: pdf-tools\n")
    back = await _import(lab.alice, response.text, space_id=lab.space_id)
    assert back.status_code == 200, back.text
    [created] = back.json()["created"]
    assert (created["path"], created["name"], created["ignored_fields"]) == (
        "SKILL.md",
        "pdf-tools",
        [],
    )
    copy = (await lab.alice.get(f"{SKILLS}/{created['skill_id']}")).json()
    assert copy["space_id"] == lab.space_id
    assert (copy["description"], copy["content"]) == (skill["description"], skill["content"])


async def test_a_zip_of_skill_folders_reports_every_skill_and_file(
    lab: Lab, session: AsyncSession
) -> None:
    await made(lab.alice, space_id=lab.space_id, name="taken")
    files: dict[str, str | bytes] = {
        "good/SKILL.md": skill_md("good"),
        "good/references/guide.md": "more text",
        "good/scripts/run.sh": "rm -rf /",
        "README.md": "about",
        "mismatch/SKILL.md": skill_md("other-name"),
        "broken/SKILL.md": "---\nname: broken\n",
        "taken/SKILL.md": skill_md("taken"),
        "nested/good/SKILL.md": skill_md("good"),
        "binary/SKILL.md": b"\xff\xfe---",
        "meta/SKILL.md": "---\nname: meta\ndescription: d\nlicense: MIT\n---\nBody\n",
        "../evil/SKILL.md": skill_md("evil"),
        ".": "nothing",
    }
    response = await _import(lab.alice, zipped(files), space_id=lab.space_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert sorted((c["path"], c["name"], c["ignored_fields"]) for c in body["created"]) == [
        ("good/SKILL.md", "good", []),
        ("meta/SKILL.md", "meta", ["license"]),
    ]
    assert sorted((s["path"], s["reason"]) for s in body["skipped"]) == [
        (".", "unsafe_path"),
        ("../evil/SKILL.md", "unsafe_path"),
        ("README.md", "not_in_skill"),
        ("binary/SKILL.md", "invalid_text"),
        ("broken/SKILL.md", "frontmatter_invalid"),
        ("good/references/guide.md", "file_unsupported"),
        ("good/scripts/run.sh", "file_unsupported"),
        ("mismatch/SKILL.md", "name_mismatch"),
        ("nested/good/SKILL.md", "duplicate"),
        ("taken/SKILL.md", "exists"),
    ]
    names = [s["name"] for s in await listed(lab.bob, space_id=lab.space_id)]
    assert names == ["good", "meta", "taken"]
    entry = await session.scalar(select(AuditLog).where(AuditLog.action == "skill.imported"))
    assert entry is not None and str(entry.target_id) == lab.space_id
    assert entry.details == {"space_id": lab.space_id, "created": 2, "skipped": 10}


async def test_an_organisation_wide_import_and_a_single_file(lab: Lab) -> None:
    response = await _import(lab.admin, zipped({"SKILL.md": skill_md("solo")}))
    assert [c["name"] for c in response.json()["created"]] == ["solo"]
    assert [s["space_id"] for s in await listed(lab.alice)] == [None]
    not_text = await _import(lab.admin, b"\xff\xfe\x00 nothing")
    assert not_text.json() == {
        "created": [],
        "skipped": [{"path": "SKILL.md", "reason": "invalid_text"}],
    }
    bad = await _import(lab.admin, skill_md("Bad_Name"))
    assert bad.json()["skipped"] == [{"path": "SKILL.md", "reason": "name_invalid"}]


async def test_importing_needs_the_right_to_manage_skills_there(lab: Lab) -> None:
    garbage = b"PK\x03\x04 not even a zip"
    bob = await _import(lab.bob, garbage, space_id=lab.space_id)
    assert (bob.status_code, bob.json()["error"]["code"]) == (403, "auth.permission_denied")
    carol = await _import(lab.carol, garbage, space_id=lab.space_id)
    assert (carol.status_code, carol.json()["error"]["code"]) == (404, "space.not_found")
    alice = await _import(lab.alice, garbage)
    assert alice.status_code == 403
    invalid = await _import(lab.alice, garbage, space_id=lab.space_id)
    assert (invalid.status_code, invalid.json()["error"]["code"]) == (422, "import.invalid_zip")


async def test_people_without_ai_import_and_export_nothing(people: Any) -> None:
    for who in ("alice", "gast"):
        client = getattr(people, who)
        response = await _import(client, skill_md("x"))
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "skill.not_found",
        )


async def test_bounds(lab: Lab, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transfer, "MAX_IMPORT_SKILLS", 2)
    files: dict[str, str | bytes] = {f"s{i}/SKILL.md": skill_md(f"s{i}") for i in range(3)}
    files["huge/SKILL.md"] = skill_md("huge", body="x" * (transfer.MAX_SKILL_MD_BYTES + 1))
    files["deep/a/b/c/d/SKILL.md"] = skill_md("d")
    body = (await _import(lab.admin, zipped(files))).json()
    assert [c["name"] for c in body["created"]] == ["s0", "s1"]
    assert sorted((s["path"], s["reason"]) for s in body["skipped"]) == [
        ("deep/a/b/c/d/SKILL.md", "too_deep"),
        ("huge/SKILL.md", "too_many"),
        ("s2/SKILL.md", "too_many"),
    ]
    monkeypatch.setattr(transfer, "MAX_IMPORT_SKILLS", 10)
    body = (await _import(lab.admin, zipped({"huge/SKILL.md": files["huge/SKILL.md"]}))).json()
    assert body["skipped"] == [{"path": "huge/SKILL.md", "reason": "too_large"}]


async def test_the_body_is_bounded(lab: Lab) -> None:
    """Its own limit, above the global one of 1 MiB."""
    above_global = await _import(lab.admin, b"x" * (2 * 1024 * 1024))
    assert above_global.status_code == 200
    assert above_global.json()["skipped"] == [{"path": "SKILL.md", "reason": "too_large"}]
    response = await _import(lab.admin, b"x" * (transfer.MAX_IMPORT_BYTES + 1))
    assert (response.status_code, response.json()["error"]["code"]) == (
        413,
        "request.too_large",
    )


async def test_export_follows_reading(lab: Lab) -> None:
    skill = await made(lab.alice, space_id=lab.space_id)
    hidden = await lab.carol.get(f"{SKILLS}/{skill['id']}/export")
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "skill.not_found")
    assert (await lab.bob.get(f"{SKILLS}/{skill['id']}/export")).status_code == 200
