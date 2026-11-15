"""Plan M8 decision 6: every tool call through `/mcp` is counted (`mcp_call`: the
token, the tool, the outcome, the time; ids only) and shown as the token's usage to
its person and to the AI administration. Nothing of a call's content goes into the
row or a log line."""

import json
import logging
from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.toolbox.base import CallContext
from app.modules.mcp_tools import service as service_module
from app.modules.mcp_tools.exposed import Exposed, tool_for
from app.modules.mcp_tools.models import McpCall
from app.modules.tokens.models import TokenMode
from app.runtime.loop import ToolResult
from tests.conftest import json_lines
from tests.factories_mcp_endpoint import Connect, text_of
from tests.factories_tokens import mcp_on, new_token
from tests.factories_wiki import Wiki, new_page, publish


async def _calls(client: AsyncClient, path: str) -> list[dict[str, object]]:
    r = await client.get(path)
    assert r.status_code == 200, r.text
    items: list[dict[str, object]] = r.json()["items"]
    return items


async def test_each_tool_call_is_counted_and_shown_as_the_tokens_usage(
    wiki: Wiki, owner: AsyncClient, connect: Connect
) -> None:
    await mcp_on(owner)
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Plan"))
    token = await new_token(wiki.editor)
    async with connect(token["secret"]) as client:
        await client.list_tools()  # not a tool call
        await client.call_tool("read_page", {"page_id": page["id"]})
        await client.call_tool("search", {})
    calls = await _calls(wiki.editor, f"/api/tokens/{token['id']}/calls")
    assert [(c["tool"], c["outcome"]) for c in calls] == [
        ("search", "invalid"),
        ("read_page", "ok"),
    ]
    assert all(isinstance(c["duration_ms"], int) and c["created_at"] for c in calls)
    assert set(calls[0]) == {"id", "tool", "outcome", "duration_ms", "created_at"}
    # The administration sees the same, as metadata of any token.
    admin = await _calls(owner, f"/api/ai/mcp/tokens/{token['id']}/calls")
    assert admin == calls
    # Paged, newest first.
    r = await wiki.editor.get(f"/api/tokens/{token['id']}/calls", params={"limit": 1})
    assert [c["tool"] for c in r.json()["items"]] == ["search"]
    later = await wiki.editor.get(
        f"/api/tokens/{token['id']}/calls", params={"limit": 1, "cursor": r.json()["next_cursor"]}
    )
    assert [c["tool"] for c in later.json()["items"]] == ["read_page"]


async def test_someone_elses_tokens_usage_answers_like_an_unknown_token(
    wiki: Wiki, owner: AsyncClient, connect: Connect
) -> None:
    await mcp_on(owner)
    token = await new_token(wiki.editor)
    r = await wiki.viewer.get(f"/api/tokens/{token['id']}/calls")
    assert r.status_code == 404 and r.json()["error"]["code"] == "token.not_found"
    r = await wiki.viewer.get(f"/api/ai/mcp/tokens/{token['id']}/calls")
    assert r.status_code == 404 and r.json()["error"]["code"] == "ai.not_found"
    await mcp_on(owner, enabled=False)
    r = await wiki.editor.get(f"/api/tokens/{token['id']}/calls")
    assert r.status_code == 404 and r.json()["error"]["code"] == "token.not_found"
    assert (await owner.get(f"/api/ai/mcp/tokens/{token['id']}/calls")).status_code == 200


@pytest.fixture
def failing_search(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    search = tool_for(TokenMode.READ, "search")
    assert search is not None

    async def boom(ctx: CallContext, args: object) -> ToolResult:
        raise RuntimeError("Zebrastreifen secret detail")

    broken = Exposed(search.spec, boom)

    def patched(mode: TokenMode, name: str) -> Exposed | None:
        return broken if name == "search" else tool_for(mode, name)

    monkeypatch.setattr(service_module, "tool_for", patched)
    yield


async def test_a_failing_call_is_a_tool_error_without_detail(
    wiki: Wiki, owner: AsyncClient, connect: Connect, failing_search: None
) -> None:
    await mcp_on(owner)
    token = await new_token(wiki.editor)
    async with connect(token["secret"]) as client:
        result = await client.call_tool("search", {"query": "Zebra"})
    assert result.is_error
    assert text_of(result) == "The call failed. Try again later."
    calls = await _calls(wiki.editor, f"/api/tokens/{token['id']}/calls")
    assert [(c["tool"], c["outcome"]) for c in calls] == [("search", "failed")]


async def test_nothing_of_a_call_goes_into_the_row_or_the_logs(
    wiki: Wiki,
    owner: AsyncClient,
    connect: Connect,
    session: AsyncSession,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    await mcp_on(owner)
    content = "Zebrastreifen-Inhalt-4711"
    page = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Plan", content_md=content)
    )
    token = await new_token(wiki.editor)
    capsys.readouterr()
    with caplog.at_level(logging.DEBUG):
        async with connect(token["secret"]) as client:
            read = await client.call_tool("read_page", {"page_id": page["id"]})
            await client.call_tool("search", {"query": "Suchbegriff-0815"})
    assert content in text_of(read)
    out = capsys.readouterr().out
    lines = json_lines(out)
    assert any(line.get("message") == "mcp.tool_call" for line in lines)
    call_lines = [line for line in lines if line.get("message") == "mcp.tool_call"]
    assert {line["tool"] for line in call_lines} == {"read_page", "search"}
    assert all(line["actor"] == f"user:{wiki.users['editor'].id}" for line in call_lines)
    logged = out + "\n".join(
        json.dumps(vars(r), default=str) + r.getMessage() for r in caplog.records
    )
    for secret in (token["secret"], token["secret"][-20:], content, "Suchbegriff-0815"):
        assert secret not in logged
    rows = (await session.scalars(select(McpCall))).all()
    assert len(rows) == 2
    for row in rows:
        values = json.dumps(
            {c.name: getattr(row, c.name) for c in McpCall.__table__.columns}, default=str
        )
        assert content not in values and "Suchbegriff" not in values
