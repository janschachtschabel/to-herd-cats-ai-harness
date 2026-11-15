"""Plan M8 task 3 (decision 3): the write tools over `/mcp`, only for `write` tokens
and only inside the token's write scope (its spaces ∩ what its person may do there).
What a token writes is its person's, with the AI mark: the token's name
(`via_token`), the source `mcp` for a page version. Pages are written directly only
where the space takes direct writes from AI (`agent_write_policy = direct`), else as
proposals. A refusal or a conflict is a tool error; every write call is audited
without content."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from mcp.shared.exceptions import MCPError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict
from app.core.permissions import SpaceRole
from app.modules.audit.models import AuditLog
from app.modules.spaces.models import AgentWritePolicy, Space, SpaceKind
from app.modules.tickets.service import TicketService
from tests.factories_mcp_endpoint import Connect, text_of
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import new_ticket
from tests.factories_tokens import mcp_on, new_token
from tests.factories_wiki import Wiki, new_page, publish

WRITE_TOOLS = {
    "comment_ticket",
    "set_ticket_status",
    "create_ticket",
    "link_ticket_page",
    "propose_page_change",
    "propose_new_page",
    "update_page",
    "post_message",
}
NOT_FOUND = "Nothing found (or not readable)."


async def _writer(wiki: Wiki, owner: AsyncClient, **fields: Any) -> dict[str, Any]:
    await mcp_on(owner)
    body = {"name": "Claude Code", "mode": "write", "space_ids": [wiki.space_id], **fields}
    return await new_token(wiki.editor, **body)


async def _thread_messages(client: AsyncClient, number: int) -> list[dict[str, Any]]:
    thread = (await client.get(f"/api/tickets/{number}/thread")).json()
    r = await client.get(f"/api/conversations/{thread['id']}/messages")
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def test_a_write_token_is_offered_the_write_tools_a_read_token_not(
    wiki: Wiki, owner: AsyncClient, connect: Connect
) -> None:
    writer = await _writer(wiki, owner)
    reader = await new_token(wiki.editor)
    async with connect(writer["secret"]) as client:
        offered = {t.name: t for t in (await client.list_tools()).tools}
    async with connect(reader["secret"]) as client:
        read_only = {t.name for t in (await client.list_tools()).tools}
        with pytest.raises(MCPError) as refused:  # no such tool for it: a protocol error
            await client.call_tool("create_ticket", {"space_id": wiki.space_id, "title": "X"})
    assert WRITE_TOOLS <= set(offered)
    assert not WRITE_TOOLS & read_only
    hints = offered["create_ticket"].annotations
    assert hints is not None and hints.read_only_hint is False
    assert refused.value.error.code == -32602


async def test_create_and_comment_a_ticket_with_the_ai_mark(
    wiki: Wiki, owner: AsyncClient, connect: Connect, session: AsyncSession
) -> None:
    token = await _writer(wiki, owner)
    async with connect(token["secret"]) as client:
        made = await client.call_tool(
            "create_ticket",
            {"space_id": wiki.space_id, "title": "Vom Client", "description_md": "Text"},
        )
        number = int(text_of(made).split("HC-")[1].rstrip("."))
        commented = await client.call_tool(
            "comment_ticket", {"key": f"HC-{number}", "text": "Erledigt bis auf Tests."}
        )
        again = await client.call_tool(
            "comment_ticket", {"key": f"HC-{number}", "text": "Erledigt bis auf Tests."}
        )
    assert not made.is_error and not commented.is_error and not again.is_error
    ticket = (await wiki.editor.get(f"/api/tickets/{number}")).json()
    assert ticket["reporter"]["id"] == str(wiki.users["editor"].id)
    assert ticket["via_token"] == "Claude Code"
    comments = [m for m in await _thread_messages(wiki.editor, number) if m["kind"] == "human"]
    assert len(comments) == 2  # each call writes; nothing is folded into the first
    for comment in comments:
        assert comment["author"]["id"] == str(wiki.users["editor"].id)
        assert comment["via_token"] == "Claude Code"
    audit = (
        await session.scalars(
            select(AuditLog).where(AuditLog.action == "mcp.write_call").order_by(AuditLog.id)
        )
    ).all()
    assert [(str(a.target_id), a.details) for a in audit] == [
        (token["id"], {"tool": "create_ticket", "outcome": "ok"}),
        (token["id"], {"tool": "comment_ticket", "outcome": "ok"}),
        (token["id"], {"tool": "comment_ticket", "outcome": "ok"}),
    ]


async def test_writes_stay_inside_the_tokens_scope(
    wiki: Wiki,
    owner: AsyncClient,
    connect: Connect,
    make_space: MakeSpace,
    session: AsyncSession,
) -> None:
    """The person may write in the other space; the token may not (its scope), and
    there it answers like a space it cannot see."""
    other = await make_space(SpaceKind.TEAM, "Anderswo", [(wiki.users["editor"], SpaceRole.EDITOR)])
    ticket = await new_ticket(wiki.editor, other.id, "Fremd")
    token = await _writer(wiki, owner)
    async with connect(token["secret"]) as client:
        made = await client.call_tool("create_ticket", {"space_id": str(other.id), "title": "X"})
        commented = await client.call_tool(
            "comment_ticket", {"key": ticket["key"], "text": "Hallo"}
        )
    assert made.is_error and text_of(made) == NOT_FOUND
    assert commented.is_error and text_of(commented) == NOT_FOUND
    listed = (await wiki.editor.get("/api/tickets", params={"space_id": str(other.id)})).json()[
        "items"
    ]
    assert [t["title"] for t in listed] == ["Fremd"]


async def test_a_viewer_writes_nothing_even_with_a_write_token(
    wiki: Wiki, owner: AsyncClient, connect: Connect
) -> None:
    await mcp_on(owner)
    token = await new_token(wiki.viewer, mode="write")
    async with connect(token["secret"]) as client:
        made = await client.call_tool("create_ticket", {"space_id": wiki.space_id, "title": "X"})
    assert made.is_error
    listed = await wiki.viewer.get("/api/tickets", params={"space_id": wiki.space_id})
    assert listed.json()["items"] == []


async def test_status_up_to_review_and_a_conflict_is_a_tool_error(
    wiki: Wiki,
    owner: AsyncClient,
    connect: Connect,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket = await new_ticket(wiki.editor, wiki.space_id, "Status")
    statuses = (await wiki.editor.get(f"/api/spaces/{wiki.space_id}/ticket-statuses")).json()
    review = next(s for s in statuses["items"] if s["category"] == "review")
    done = next(s for s in statuses["items"] if s["category"] == "done")
    token = await _writer(wiki, owner)
    async with connect(token["secret"]) as client:
        moved = await client.call_tool(
            "set_ticket_status", {"key": ticket["key"], "status": review["name"]}
        )
        finished = await client.call_tool(
            "set_ticket_status", {"key": ticket["key"], "status": done["name"]}
        )

        async def raced(*args: object, **kwargs: object) -> None:
            raise Conflict(code="ticket.version_conflict")

        monkeypatch.setattr(TicketService, "update", raced)
        conflict = await client.call_tool(
            "set_ticket_status", {"key": ticket["key"], "status": review["name"]}
        )
    assert not moved.is_error
    assert finished.is_error and "done" in text_of(finished)
    assert conflict.is_error
    assert text_of(conflict) == "Changed meanwhile (ticket.version_conflict): read it again."
    shown = (await wiki.editor.get(f"/api/tickets/{ticket['number']}")).json()
    assert shown["status"]["id"] == review["id"]


async def test_pages_are_proposed_unless_the_space_takes_direct_writes(
    wiki: Wiki, owner: AsyncClient, connect: Connect, session: AsyncSession
) -> None:
    page = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="Alt")
    )
    token = await _writer(wiki, owner)
    change = {"page_id": page["id"], "content_md": "Neu", "reason": "Klarer"}
    async with connect(token["secret"]) as client:
        direct = await client.call_tool("update_page", change)
        proposed = await client.call_tool("propose_page_change", change)
        new = await client.call_tool(
            "propose_new_page",
            {"space_id": wiki.space_id, "title": "Neu", "content_md": "Text", "reason": "Fehlt"},
        )
    assert direct.is_error and "propose" in text_of(direct)
    assert not proposed.is_error and not new.is_error
    r = await wiki.moderator.get(f"/api/spaces/{wiki.space_id}/proposals")
    proposals = r.json()["items"]
    assert len(proposals) == 2
    for proposal in proposals:
        assert proposal["author"]["id"] == str(wiki.users["editor"].id)
        assert proposal["ai"] is True and proposal["via_token"] == "Claude Code"
    # The moderator accepts: the version is the author's, with the mark.
    change_one = next(p for p in proposals if p["kind"] == "change")
    accepted = await wiki.moderator.post(
        f"/api/proposals/{change_one['id']}/accept", json={"version": change_one["version"]}
    )
    assert accepted.status_code == 200, accepted.text
    versions = (await wiki.editor.get(f"/api/pages/{page['id']}/versions")).json()["items"]
    assert versions[0]["ai"] is True and versions[0]["via_token"] == "Claude Code"


async def test_a_direct_page_write_in_two_steps_with_source_mcp(
    wiki: Wiki, owner: AsyncClient, connect: Connect, session: AsyncSession
) -> None:
    space = await session.get(Space, uuid.UUID(wiki.space_id))
    assert space is not None
    space.agent_write_policy = AgentWritePolicy.DIRECT
    await session.flush()
    page = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="Alt")
    )
    token = await _writer(wiki, owner)
    change = {"page_id": page["id"], "content_md": "Neu", "reason": "Klarer"}
    async with connect(token["secret"]) as client:
        preview = await client.call_tool("update_page", change)
        key = text_of(preview).split('token="')[1].split('"')[0]
        saved = await client.call_tool("update_page", {**change, "token": key})
    assert not preview.is_error and "+ Neu" in text_of(preview)
    assert not saved.is_error, text_of(saved)
    shown = (await wiki.editor.get(f"/api/pages/{page['id']}")).json()
    assert shown["content_md"] == "Neu"
    newest = (await wiki.editor.get(f"/api/pages/{page['id']}/versions")).json()["items"][0]
    assert newest["source"] == "mcp" and newest["ai"] is True
    assert newest["author"]["id"] == str(wiki.users["editor"].id)
    assert newest["via_token"] == "Claude Code"


async def test_messages_go_to_channels_of_the_scope_only(
    wiki: Wiki, owner: AsyncClient, connect: Connect, make_space: MakeSpace
) -> None:
    channel = await wiki.moderator.post(
        f"/api/spaces/{wiki.space_id}/channels", json={"name": "allgemein"}
    )
    assert channel.status_code == 201, channel.text
    dm = await wiki.editor.post("/api/dms", json={"user_ids": [str(wiki.users["viewer"].id)]})
    assert dm.status_code in (200, 201), dm.text
    token = await _writer(wiki, owner)
    async with connect(token["secret"]) as client:
        posted = await client.call_tool(
            "post_message", {"conversation_id": channel.json()["id"], "text": "Build ist grün."}
        )
        private = await client.call_tool(
            "post_message", {"conversation_id": dm.json()["id"], "text": "Psst"}
        )
    assert not posted.is_error, text_of(posted)
    assert private.is_error and text_of(private) == NOT_FOUND
    r = await wiki.viewer.get(f"/api/conversations/{channel.json()['id']}/messages")
    [message] = r.json()["items"]
    assert message["body_md"] == "Build ist grün."
    assert message["author"]["id"] == str(wiki.users["editor"].id)
    assert message["kind"] == "human" and message["via_token"] == "Claude Code"
    dm_messages = await wiki.viewer.get(f"/api/conversations/{dm.json()['id']}/messages")
    assert dm_messages.json()["items"] == []


async def test_a_link_between_a_ticket_and_a_page(
    wiki: Wiki, owner: AsyncClient, connect: Connect
) -> None:
    ticket = await new_ticket(wiki.editor, wiki.space_id, "Mit Seite")
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Doku"))
    token = await _writer(wiki, owner)
    async with connect(token["secret"]) as client:
        linked = await client.call_tool(
            "link_ticket_page", {"key": ticket["key"], "page_id": page["id"]}
        )
    assert not linked.is_error, text_of(linked)
    pages = (await wiki.editor.get(f"/api/tickets/{ticket['number']}/pages")).json()
    assert [p["id"] for p in pages["items"]] == [page["id"]]
