"""Module review M8 2, probe: `/mcp` and the token API with the ids of another
organisation. A token of organisation A, held by A's owner with a write token over
every space, names B's space, page, conversation and message in every tool that takes
an id: each answers exactly like an unknown id, and nothing is written in B. A token
cannot be scoped to B's space."""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.principal import Principal, SystemRole
from app.modules.messaging.channels import ChannelService
from app.modules.messaging.models import Message
from app.modules.messaging.service import MessageService
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space, SpaceKind
from app.modules.tickets.models import WorkItem
from app.modules.tickets.service import TicketService
from app.modules.wiki.models import Page
from app.modules.wiki.service import PageService
from tests.factories_mcp_endpoint import Connect, text_of
from tests.factories_tickets import new_ticket
from tests.factories_tokens import mcp_on, new_token
from tests.factories_wiki import new_page, publish


async def _count(session: AsyncSession, model: Any, org_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(model).where(model.org_id == org_id)
    return int(await session.scalar(stmt) or 0)


async def test_another_organisations_ids_answer_like_unknown_ones(
    session: AsyncSession, owner: AsyncClient, make_user: Any, connect: Connect
) -> None:
    other = Organization(name="Fremd GmbH")
    session.add(other)
    await session.flush()
    stranger = await make_user(SystemRole.OWNER, organization=other)
    actor = Actor(other.id, Principal.user(stranger.id), SystemRole.OWNER, frozenset())
    space = Space(org_id=other.id, kind=SpaceKind.OPEN, name="Fremd offen")
    session.add(space)
    await session.flush()
    theirs = str(space.id)
    made = await PageService(session).create(actor, space.id, None, "Zebra fremd", "Zebrageheimnis")
    made = await PageService(session).publish(actor, made.id, made.version)
    page = {"id": str(made.id)}
    await TicketService(session).create(actor, space.id, title="Zebra-Ticket fremd")
    conversation = await ChannelService(session).create(actor, space.id, "fremdkanal", None)
    channel = str(conversation.id)
    posted = await MessageService(session).post(actor, conversation.id, "Zebra hallo")
    message = str(getattr(posted, "id", None) or posted.message.id)

    r = await owner.post("/api/spaces", json={"name": "Eigen", "kind": "open"})
    assert r.status_code == 201, r.text
    ours = r.json()["id"]
    our_ticket = await new_ticket(owner, ours, "Eigenes Ticket")
    our_page = await publish(owner, await new_page(owner, ours, "Eigene Seite", content_md="x"))
    await mcp_on(owner)

    r = await owner.post(
        "/api/tokens",
        json={"name": "X", "mode": "read", "expires_in_days": 30, "space_ids": [theirs]},
    )
    assert r.status_code in (404, 422), r.text  # no token over another organisation's space

    token = await new_token(owner, mode="write")
    before = [await _count(session, m, other.id) for m in (Page, WorkItem, Message)]
    key = f"HC-{our_ticket['number']}"
    calls: list[tuple[str, dict[str, Any]]] = [
        ("read_page", {"page_id": page["id"]}),
        ("list_versions", {"page_id": page["id"]}),
        ("list_tree", {"space_id": theirs}),
        ("search_tickets", {"space_id": theirs}),
        ("create_ticket", {"space_id": theirs, "title": "eingeschleust"}),
        ("propose_new_page", {"space_id": theirs, "title": "e", "content_md": "e", "reason": "e"}),
        (
            "propose_new_page",
            {
                "space_id": ours,
                "parent_id": page["id"],
                "title": "e",
                "content_md": "e",
                "reason": "e",
            },
        ),
        ("propose_page_change", {"page_id": page["id"], "content_md": "e", "reason": "e"}),
        ("update_page", {"page_id": page["id"], "content_md": "e", "reason": "e"}),
        ("link_ticket_page", {"key": key, "page_id": page["id"]}),
        ("post_message", {"conversation_id": channel, "text": "eingeschleust"}),
        ("post_message", {"conversation_id": channel, "text": "e", "reply_to": message}),
    ]
    async with connect(token["secret"]) as client:
        offered = {t.name for t in (await client.list_tools()).tools}
        answers = {}
        for i, (name, args) in enumerate(calls):
            assert name in offered, name
            answers[i] = (name, text_of(await client.call_tool(name, args)))
        found = text_of(await client.call_tool("search", {"query": "Zebra"}))
        listed = text_of(await client.call_tool("search_tickets", {"query": "Zebra"}))
        tree = text_of(await client.call_tool("list_tree", {}))
        own_link = text_of(
            await client.call_tool("link_ticket_page", {"key": key, "page_id": our_page["id"]})
        )
    for name, text in answers.values():
        assert "Zebra" not in text and "fremd" not in text.lower(), (name, text)
        assert "found" in text.lower() or "not allowed" in text.lower(), (name, text)
    assert "Zebra" not in found and "Zebra" not in listed and "Fremd" not in tree
    assert "found" not in own_link.lower(), own_link  # the probe's calls are well-formed
    assert [await _count(session, m, other.id) for m in (Page, WorkItem, Message)] == before
    links = (await owner.get(f"/api/tickets/{our_ticket['number']}/pages")).json()
    assert page["id"] not in str(links)
