"""Writes per person and minute are limited (ASVS 5.0 V2.4.1, plan M9 task 18, J10):
messages, pages, tickets and the like count together, uploads apart; beyond the limit
429 `rate.limited` with `Retry-After`. An agent's writes count like a person's, on its
own count."""

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.metrics import REGISTRY
from app.modules.agents.toolbox import message_tools
from tests.factories_tools import tool_context
from tests.factories_wiki import Wiki, new_page, publish
from tests.factories_writing import Work

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _limited(area: str) -> float:
    return REGISTRY.get_sample_value("herd_rate_limited_total", {"area": area}) or 0.0


def _refused(answer: object) -> int:
    assert answer.status_code == 429, answer.text  # type: ignore[attr-defined]
    assert answer.json()["error"]["code"] == "rate.limited"  # type: ignore[attr-defined]
    wait = int(answer.headers["retry-after"])  # type: ignore[attr-defined]
    assert 1 <= wait <= 60
    return wait


async def _channel(client: AsyncClient, space_id: str) -> str:
    made = await client.post(f"/api/spaces/{space_id}/channels", json={"name": "takt"})
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


async def test_writes_beyond_the_limit_answer_429_with_retry_after(
    wiki: Wiki, monkeypatch: pytest.MonkeyPatch
) -> None:
    channel = await _channel(wiki.admin, wiki.space_id)  # before the limit is set
    monkeypatch.setattr(get_settings(), "write_rate_per_minute", 3)
    editor: AsyncClient = wiki.editor
    before = _limited("write")
    page = await new_page(editor, wiki.space_id, "Takt")  # 1
    await publish(editor, page)  # 2
    sent = await editor.post(f"/api/conversations/{channel}/messages", json={"body_md": "a"})
    assert sent.status_code == 201, sent.text  # 3
    _refused(await editor.post(f"/api/conversations/{channel}/messages", json={"body_md": "b"}))
    _refused(await editor.post(f"/api/spaces/{wiki.space_id}/tickets", json={"title": "c"}))
    assert _limited("write") == before + 2
    # Reading goes on; somebody else still writes.
    assert (await editor.get(f"/api/pages/{page['id']}")).status_code == 200
    other = await wiki.editor2.post(f"/api/conversations/{channel}/messages", json={"body_md": "d"})
    assert other.status_code == 201, other.text


async def test_uploads_count_apart_from_other_writes(
    wiki: Wiki, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Bilder")
    monkeypatch.setattr(get_settings(), "upload_rate_per_minute", 1)
    monkeypatch.setattr(get_settings(), "write_rate_per_minute", 50)
    url = f"/api/pages/{page['id']}/attachments"
    headers = {"Content-Type": "application/octet-stream"}
    first = await wiki.editor.post(url, params={"filename": "a.png"}, content=PNG, headers=headers)
    assert first.status_code == 201, first.text
    before = _limited("upload")
    _refused(
        await wiki.editor.post(url, params={"filename": "b.png"}, content=PNG, headers=headers)
    )
    assert _limited("upload") == before + 1
    assert (await publish(wiki.editor, page))["id"] == page["id"]  # writes still pass


async def test_agents_count_like_people(work: Work, monkeypatch: pytest.MonkeyPatch) -> None:
    """A run's writing tools count on the agent's own count: beyond the limit the tool
    answers that it was refused, and nothing is written."""
    monkeypatch.setattr(get_settings(), "write_rate_per_minute", 2)
    ctx = await tool_context(work.bench)
    texts = []
    for i in range(3):
        args = message_tools.PostMessageArgs(conversation_id=work.bench.dm_id, text=f"Nr. {i}")
        texts.append((await message_tools.post_message(ctx, args)).text)
    assert texts[0].startswith("Posted") and texts[1].startswith("Posted")
    assert texts[2] == "Refused (rate.limited)."
    # Alice herself is a different count.
    said = await work.bench.say("Ich schreibe noch")
    assert said["id"]
