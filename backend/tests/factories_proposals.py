"""Proposal helpers on the `wiki` fixture: an agent's run actor (the person who asked,
held to the agent's role in the wiki space; the agent need not exist as a row, the
service takes the author from its caller), making proposals through the service
(there is no route), and reading and deciding them through the API."""

import uuid
from dataclasses import replace
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor, ReadScope
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.proposals.models import PageProposal
from app.modules.proposals.service import ProposalService
from tests.factories_wiki import Wiki
from tests.test_access import actor_of

AGENT = Principal.agent(uuid.UUID("01900000-0000-7000-8000-00000000a6e7"))
RUN_ID = uuid.UUID("01900000-0000-7000-8000-0000000000aa")


async def run_actor(
    session: AsyncSession, wiki: Wiki, person: str = "editor", role: SpaceRole = SpaceRole.EDITOR
) -> Actor:
    """The actor of an agent's run that `person` started, the agent being `role` in
    the wiki space only."""
    actor = await actor_of(session, wiki.users[person])
    return replace(actor, read_scope=ReadScope.of({wiki.space.id: role}))


async def agent_change(
    session: AsyncSession,
    wiki: Wiki,
    page: dict[str, Any],
    content_md: str,
    reason: str = "Tippfehler",
    *,
    person: str = "editor",
) -> PageProposal:
    actor = await run_actor(session, wiki, person)
    return await ProposalService(session).propose_change(
        actor, uuid.UUID(page["id"]), content_md, reason, author=AGENT, run_id=RUN_ID
    )


async def agent_new(
    session: AsyncSession,
    wiki: Wiki,
    title: str,
    content_md: str,
    parent: dict[str, Any] | None = None,
    reason: str = "Fehlt noch",
) -> PageProposal:
    actor = await run_actor(session, wiki)
    parent_id = uuid.UUID(parent["id"]) if parent else None
    return await ProposalService(session).propose_new(
        actor, wiki.space.id, parent_id, title, content_md, reason, author=AGENT, run_id=RUN_ID
    )


async def detail(client: AsyncClient, proposal: PageProposal | dict[str, Any]) -> Any:
    pid = proposal["id"] if isinstance(proposal, dict) else proposal.id
    r = await client.get(f"/api/proposals/{pid}")
    assert r.status_code == 200, r.text
    return r.json()


async def accept(client: AsyncClient, proposal: PageProposal, **body: Any) -> Any:
    body.setdefault("version", proposal.version)
    return await client.post(f"/api/proposals/{proposal.id}/accept", json=body)


async def reject(client: AsyncClient, proposal: PageProposal, **body: Any) -> Any:
    body.setdefault("version", proposal.version)
    return await client.post(f"/api/proposals/{proposal.id}/reject", json=body)


async def listed(client: AsyncClient, space_id: object, **params: Any) -> Any:
    r = await client.get(f"/api/spaces/{space_id}/proposals", params=params)
    assert r.status_code == 200, r.text
    return r.json()
