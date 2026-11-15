"""Plan M8 task 4, carry-in (decision 3): what a token writes carries the AI mark, and
so do the system timeline entries its writes cause. A status change, a page link and a
page proposal made through `/mcp` write timeline entries whose `via_token` is the
token's name, like the direct writes; the same changes made in the app carry none.

The outbox events carry the token's id only (ids, never text, spec 4.3); the timeline
handlers look its name up."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.proposals.handlers import write_entry
from tests.factories_mcp_endpoint import Connect
from tests.factories_tickets import new_ticket
from tests.factories_tokens import mcp_on, new_token
from tests.factories_wiki import Wiki, new_page, publish
from tests.ticket_thread_helpers import ticket_handlers


async def _messages(client: AsyncClient, conversation_id: str) -> list[dict[str, Any]]:
    r = await client.get(f"/api/conversations/{conversation_id}/messages", params={"limit": 100})
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def _system(client: AsyncClient, conversation_id: str) -> dict[str, str | None]:
    """The thread's system entries: their key → `via_token`."""
    found: dict[str, str | None] = {}
    for message in await _messages(client, conversation_id):
        if message["kind"] == "system":
            found[message["system"]["key"]] = message["via_token"]
    return found


async def test_timeline_entries_of_token_writes_carry_the_tokens_name(
    wiki: Wiki, owner: AsyncClient, connect: Connect, session: AsyncSession
) -> None:
    await mcp_on(owner)
    ticket = await new_ticket(wiki.editor, wiki.space_id, "Markiert")
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Seite"))
    statuses = (await wiki.editor.get(f"/api/spaces/{wiki.space_id}/ticket-statuses")).json()
    active = next(s for s in statuses["items"] if s["category"] == "active")
    token = await new_token(
        wiki.editor, name="Claude Code", mode="write", space_ids=[wiki.space_id]
    )
    async with connect(token["secret"]) as client:
        moved = await client.call_tool(
            "set_ticket_status", {"key": ticket["key"], "status": active["name"]}
        )
        linked = await client.call_tool(
            "link_ticket_page", {"key": ticket["key"], "page_id": page["id"]}
        )
    assert not moved.is_error and not linked.is_error
    await ticket_handlers(session)
    thread = (await wiki.editor.get(f"/api/tickets/{ticket['number']}/thread")).json()
    entries = await _system(wiki.editor, thread["id"])
    assert entries["ticket.created"] is None  # made in the app
    assert entries["ticket.status_changed"] == "Claude Code"
    assert entries["ticket.page_linked"] == "Claude Code"
    events = (
        await session.scalars(select(EventOutbox).where(EventOutbox.subject_type == "ticket"))
    ).all()
    for event in events:
        assert "Claude Code" not in str(event.payload)  # the id, never the name


async def test_a_proposals_page_entry_carries_the_tokens_name(
    wiki: Wiki, owner: AsyncClient, connect: Connect, session: AsyncSession
) -> None:
    await mcp_on(owner)
    page = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="Alt")
    )
    token = await new_token(wiki.editor, name="Codex", mode="write", space_ids=[wiki.space_id])
    async with connect(token["secret"]) as client:
        proposed = await client.call_tool(
            "propose_page_change",
            {"page_id": page["id"], "content_md": "Neu", "reason": "Klarer"},
        )
    assert not proposed.is_error
    rows = (
        await session.scalars(select(EventOutbox).where(EventOutbox.subject_type == "proposal"))
    ).all()
    for row in rows:
        await write_entry(session, Event.of(row))
    thread = (await wiki.editor.get(f"/api/pages/{page['id']}/thread")).json()
    entries = await _system(wiki.editor, thread["id"])
    assert entries["proposal.created"] == "Codex"
