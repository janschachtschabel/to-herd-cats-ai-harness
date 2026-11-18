"""Proposal events (plan M6 task 5): `proposal.*` through the outbox with ids only, a
system entry in the page's thread (no content), `proposal` activity entries for the
space's moderators on creation and for a person author on a decision, live as
`proposal.changed` with ids. Handlers run here in the test's transaction, as the
worker would, more than once where that matters; nothing goes into a channel."""

import json
import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.live_decode import decode
from app.modules.messaging.live_events import of_event
from app.modules.messaging.models import Conversation, ConversationKind, Message
from app.modules.messaging.notification_models import Notification
from app.modules.proposals.events import PROPOSAL_EVENTS
from app.modules.proposals.handlers import notify_on_proposal, proposal_timeline
from app.modules.proposals.service import ProposalService
from app.worker.registry import REGISTRY
from tests.factories_proposals import AGENT, accept, agent_change, agent_new, reject
from tests.factories_wiki import Wiki, new_page
from tests.test_access import actor_of

SECRETS = ("Geheimer Titel", "geheimer Inhalt", "geheimer Grund")


async def _events(session: AsyncSession) -> list[EventOutbox]:
    rows = await session.scalars(
        select(EventOutbox).where(EventOutbox.type.in_(PROPOSAL_EVENTS)).order_by(EventOutbox.id)
    )
    return list(rows.all())


async def _handle(session: AsyncSession, *, notify_first: bool = False, times: int = 1) -> None:
    handlers = [proposal_timeline, notify_on_proposal]
    if notify_first:
        handlers.reverse()
    for _ in range(times):
        for row in await _events(session):
            for handle in handlers:
                await handle(session, Event.of(row))


async def _for_me(client: AsyncClient) -> list[tuple[str, str | None]]:
    r = await client.get("/api/activity")
    assert r.status_code == 200, r.text
    return [(e["reason"], e["conversation"]["page_id"]) for e in r.json()["items"]]


async def _entries(session: AsyncSession, page_id: object) -> list[dict[str, Any]]:
    rows = await session.scalars(
        select(Message.body_md)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.page_id == uuid.UUID(str(page_id)), Message.author_type == "system")
        .order_by(Message.id)
    )
    return [json.loads(body) for body in rows.all()]


def test_the_worker_knows_the_handlers() -> None:
    import app.worker.handlers  # noqa: F401, PLC0415

    names = {h.name for h in REGISTRY.for_type("proposal.created")}
    assert {"proposal_timeline", "notify_on_proposal", "publish_live"} <= names


async def test_events_carry_ids_only(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, SECRETS[0], content_md="alt")
    proposal = await agent_change(session, wiki, page, SECRETS[1], SECRETS[2])
    parent_less = await agent_new(session, wiki, SECRETS[0], SECRETS[1], None, SECRETS[2])
    assert (await reject(wiki.moderator, parent_less, reason=SECRETS[2])).status_code == 200
    assert (await accept(wiki.moderator, proposal)).status_code == 200
    rows = await _events(session)
    assert [r.type for r in rows] == [
        "proposal.created",
        "proposal.created",
        "proposal.rejected",
        "proposal.accepted",
    ]
    for row in rows:
        assert row.subject_type == "proposal" and row.space_id == wiki.space.id
        assert set(row.payload) == {"proposal_id", "page_id"}
        text = json.dumps(row.payload)
        assert not any(secret in text for secret in SECRETS)
    assert rows[0].payload == {"proposal_id": str(proposal.id), "page_id": page["id"]}
    assert rows[1].payload == {"proposal_id": str(parent_less.id), "page_id": None}
    live = of_event(Event.of(rows[3]))
    assert live is not None and live.name == "proposal.changed"
    assert (live.space_id, live.proposal_id, live.conversation_id, live.user_id) == (
        wiki.space.id,
        proposal.id,
        None,
        None,
    )
    assert json.loads(live.frame().decode().split("data: ")[1]) == {
        "space_id": wiki.space_id,
        "proposal_id": str(proposal.id),
    }
    again = decode(live.payload())
    assert again is not None and again.proposal_id == proposal.id
    assert not any(secret in live.payload() for secret in SECRETS)


async def test_the_page_thread_tells_without_content(wiki: Wiki, session: AsyncSession) -> None:
    parent = await new_page(wiki.editor, wiki.space_id, "Handbuch", content_md="alt")
    change = await agent_change(session, wiki, parent, "neu")
    new = await agent_new(session, wiki, "Urlaub", "x", parent)
    top = await agent_new(session, wiki, "Oben", "x")
    assert (await accept(wiki.moderator, change)).status_code == 200
    assert (await reject(wiki.moderator, top)).status_code == 200
    await _handle(session, times=2)
    moderator, agent = str(wiki.users["moderator"].id), str(AGENT.id)
    assert await _entries(session, parent["id"]) == [  # an agent's proposal names the agent
        {"key": "proposal.created", "actor": agent},
        {"key": "proposal.created", "actor": agent},
        {"key": "proposal.accepted", "actor": moderator},
    ]
    thread = (await wiki.editor.get(f"/api/pages/{parent['id']}/thread")).json()
    assert thread["kind"] == "thread_page"
    assert new.parent_id == uuid.UUID(parent["id"])
    channels = await session.scalar(
        select(func.count())
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.kind == ConversationKind.CHANNEL)
    )
    assert channels == 0


async def test_moderators_hear_of_a_new_proposal(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="alt")
    await agent_change(session, wiki, page, "neu")
    await _handle(session, notify_first=True, times=2)
    assert await _for_me(wiki.moderator) == [("proposal", page["id"])]
    for nobody in ("editor", "editor2", "viewer", "outsider", "admin"):
        assert await _for_me(wiki.clients[nobody]) == [], nobody
    (entry,) = (await wiki.moderator.get("/api/activity")).json()["items"]
    assert entry["snippet"] == ""
    count = await session.scalar(select(func.count()).select_from(Notification))
    assert count == 1


async def test_a_person_author_hears_of_the_decision(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="alt")
    editor = await actor_of(session, wiki.users["editor2"])
    service = ProposalService(session)
    mine = await service.propose_change(
        editor, uuid.UUID(page["id"]), "neu", "Bitte", author=editor.principal
    )
    agents = await agent_change(session, wiki, page, "anders")
    assert (await reject(wiki.moderator, mine)).status_code == 200
    assert (await reject(wiki.moderator, agents)).status_code == 200
    await _handle(session)
    assert await _for_me(wiki.editor2) == [("proposal", page["id"])]
    # The run's person is not the author: an agent's decision tells nobody.
    assert await _for_me(wiki.editor) == []
    reasons = (await session.scalars(select(Notification.reason))).all()
    assert sorted(reasons) == ["proposal", "proposal", "proposal"]  # 2 moderator, 1 author
