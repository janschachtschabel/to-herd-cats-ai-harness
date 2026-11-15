"""Proposal decisions that race, over separate connections with real commits
(tests/real_db.py): two accepts, accept against reject, accept against a page save,
the trash and the AI lock. The proposal's row lock decides between decisions; the
page's row lock between a decision and a page write, so a decision never writes
over a save it did not see, into the trash, or into a page locked for AI."""

import asyncio
import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.access import actor_for
from app.core.principal import Principal
from app.modules.auth.context import AuthContext
from app.modules.proposals.models import PageProposal
from app.modules.proposals.service import ProposalService
from app.modules.users.models import User
from app.modules.wiki.models import Page, PageVersion
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

AGENT = Principal.agent(uuid.UUID("01900000-0000-7000-8000-00000000a6e7"))
ROUNDS = 4


async def _setup(make_real_client: MakeRealClient, real_db: RealDb) -> tuple[AsyncClient, str]:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space = (await owner.post("/api/spaces", json={"name": "Race", "kind": "team"})).json()
    return owner, space["id"]


async def _page(owner: AsyncClient, space_id: str, content: str = "alt") -> dict[str, Any]:
    r = await owner.post(
        f"/api/spaces/{space_id}/pages", json={"title": "Seite", "content_md": content}
    )
    assert r.status_code == 201, r.text
    page: dict[str, Any] = r.json()
    return page


async def _propose(real_db: RealDb, page: dict[str, Any], content: str = "neu") -> str:
    """An agent's proposal, committed (the owner's actor stands in for the run)."""
    async with real_db.database.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == real_db.owner_email))
        assert user is not None
        actor = await actor_for(session, AuthContext(user=user))
        proposal = await ProposalService(session).propose_change(
            actor, uuid.UUID(page["id"]), content, "Grund", author=AGENT
        )
        await session.commit()
        return str(proposal.id)


async def _state(real_db: RealDb, proposal_id: str) -> tuple[str, int]:
    async with real_db.database.session_factory() as session:
        row = await session.get(PageProposal, uuid.UUID(proposal_id))
        assert row is not None
        return row.state, row.version


async def _content(real_db: RealDb, page_id: str) -> tuple[str, int]:
    async with real_db.database.session_factory() as session:
        page = await session.get(Page, uuid.UUID(page_id))
        versions = await session.scalar(
            select(func.count()).select_from(PageVersion).where(PageVersion.page_id == page_id)
        )
        assert page is not None
        return page.content_md, int(versions or 0)


async def test_two_accepts_write_once(real_db: RealDb, make_real_client: MakeRealClient) -> None:
    owner, space_id = await _setup(make_real_client, real_db)
    for _ in range(ROUNDS):
        page = await _page(owner, space_id)
        pid = await _propose(real_db, page)
        responses = await asyncio.gather(
            *(owner.post(f"/api/proposals/{pid}/accept", json={"version": 1}) for _ in range(3))
        )
        assert sorted(r.status_code for r in responses) == [200, 409, 409]
        codes = {r.json()["error"]["code"] for r in responses if r.status_code == 409}
        assert codes == {"proposal.not_open"}
        assert await _content(real_db, page["id"]) == ("neu", 2)  # one version written


async def test_accept_against_reject_has_one_winner(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, space_id = await _setup(make_real_client, real_db)
    for _ in range(ROUNDS):
        page = await _page(owner, space_id)
        pid = await _propose(real_db, page)
        accepted, rejected = await asyncio.gather(
            owner.post(f"/api/proposals/{pid}/accept", json={"version": 1}),
            owner.post(f"/api/proposals/{pid}/reject", json={"version": 1}),
        )
        assert sorted([accepted.status_code, rejected.status_code]) == [200, 409]
        state, version = await _state(real_db, pid)
        assert version == 2
        expected = ("neu", 2) if accepted.status_code == 200 else ("alt", 1)
        assert state == ("accepted" if accepted.status_code == 200 else "rejected")
        assert await _content(real_db, page["id"]) == expected


async def test_accept_never_writes_over_a_save_it_did_not_see(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, space_id = await _setup(make_real_client, real_db)
    for _ in range(ROUNDS):
        page = await _page(owner, space_id, "eins\nzwei\ndrei")
        pid = await _propose(real_db, page, "EINS\nzwei\ndrei")
        accepted, saved = await asyncio.gather(
            owner.post(f"/api/proposals/{pid}/accept", json={"version": 1}),
            owner.patch(
                f"/api/pages/{page['id']}",
                json={"content_md": "eins\nzwei\nDREI", "version": page["version"]},
            ),
        )
        content, _ = await _content(real_db, page["id"])
        if accepted.status_code == 200:
            # The accept came first; the save then named a stale version.
            assert saved.status_code == 409 and content == "EINS\nzwei\ndrei"
        else:
            # The save came first; the accept saw the page moved on and applied nothing.
            assert saved.status_code == 200 and content == "eins\nzwei\nDREI"
            error = accepted.json()["error"]
            assert error["code"] == "proposal.base_outdated"
            assert error["details"]["merged_content"] == "EINS\nzwei\nDREI"
            assert await _state(real_db, pid) == ("open", 1)


async def test_accept_against_the_trash_and_the_ai_lock(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, space_id = await _setup(make_real_client, real_db)
    for round_ in range(ROUNDS):
        page = await _page(owner, space_id)
        pid = await _propose(real_db, page)
        if round_ % 2:
            other = owner.post(f"/api/pages/{page['id']}/trash", json={"version": 1})
        else:
            other = owner.put(
                f"/api/pages/{page['id']}/ai-lock", json={"no_ai": True, "version": 1}
            )
        accepted, blocked = await asyncio.gather(
            owner.post(f"/api/proposals/{pid}/accept", json={"version": 1}), other
        )
        content, versions = await _content(real_db, page["id"])
        if accepted.status_code == 200:
            # The decision came first: the trash or the lock then named a stale version.
            assert blocked.status_code == 409, blocked.text
            assert (content, versions) == ("neu", 2)
        else:
            assert blocked.status_code in (200, 204), blocked.text
            assert accepted.status_code in (404, 409), accepted.text
            code = accepted.json()["error"]["code"]
            assert code in {"proposal.not_found", "proposal.page_trashed", "proposal.page_no_ai"}
            assert (content, versions) == ("alt", 1)
            assert (await _state(real_db, pid))[0] == "open"
