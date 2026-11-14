"""Page proposals (plan M6 task 5): made through the service by an agent's run, listed
and read with their diff by page editors, accepted or rejected by moderators; an
accepted change is a Markdown save written for the agent (version source `agent`,
the run, the reason as change text, a new generation)."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound, ValidationFailed
from app.core.principal import Principal
from app.modules.proposals.models import PageProposal
from app.modules.proposals.service import ProposalService
from app.modules.wiki.models import Page
from tests.factories_proposals import (
    AGENT,
    RUN_ID,
    accept,
    agent_change,
    agent_new,
    detail,
    listed,
    reject,
    run_actor,
)
from tests.factories_wiki import Wiki, new_page, publish
from tests.test_access import actor_of


async def _page_row(session: AsyncSession, page_id: object) -> Page:
    page = await session.scalar(
        select(Page)
        .where(Page.id == uuid.UUID(str(page_id)))
        .execution_options(populate_existing=True)
    )
    assert page is not None
    return page


async def test_a_change_is_proposed_listed_and_read(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="eins\nzwei\n")
    proposal = await agent_change(session, wiki, page, "eins\nZWEI\n")
    items = (await listed(wiki.editor2, wiki.space_id))["items"]
    assert [i["id"] for i in items] == [str(proposal.id)]
    item = items[0]
    assert (item["kind"], item["state"], item["page_id"], item["base_version"]) == (
        "change",
        "open",
        page["id"],
        1,
    )
    assert item["author"] == {"type": "agent", "id": str(AGENT.id), "name": None}
    assert (item["ai"], item["run_id"], item["reason"], item["version"]) == (
        True,
        str(RUN_ID),
        "Tippfehler",
        1,
    )
    assert "content_md" not in item
    one = await detail(wiki.moderator, proposal)
    assert one["content_md"] == "eins\nZWEI\n"
    assert one["diff"] == [
        {"kind": "equal", "lines": ["eins"]},
        {"kind": "delete", "lines": ["zwei"]},
        {"kind": "insert", "lines": ["ZWEI"]},
    ]
    assert (one["too_large"], one["current_content_md"], one["merge"]) == (False, None, None)
    assert one["page_version"] == page["version"]


async def test_accepting_writes_a_version_for_the_agent(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="alt")
    proposal = await agent_change(session, wiki, page, "neu", "Aktualisiert")
    r = await accept(wiki.moderator, proposal)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["state"], out["result_version"], out["version"]) == ("accepted", 2, 2)
    assert out["decided_by"] == {
        "id": str(wiki.users["moderator"].id),
        "name": wiki.users["moderator"].name,
    }
    assert out["decided_at"] is not None and out["decision_reason"] is None
    row = await _page_row(session, page["id"])
    assert row.content_md == "neu"
    assert row.collab_generation == 1  # open live sessions end
    assert (row.updated_by_type, row.updated_by_id) == (AGENT.type, AGENT.id)
    newest = (await wiki.editor.get(f"/api/pages/{page['id']}/versions")).json()["items"][0]
    assert (newest["number"], newest["source"], newest["change_summary"]) == (
        2,
        "agent",
        "Aktualisiert",
    )
    assert (newest["author"]["type"], newest["run_id"], newest["ai"]) == (
        "agent",
        str(RUN_ID),
        True,
    )
    again = await accept(wiki.moderator, proposal, version=2)
    assert again.status_code == 409 and again.json()["error"]["code"] == "proposal.not_open"


async def test_rejecting_keeps_the_page_and_the_reason(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="alt")
    proposal = await agent_change(session, wiki, page, "neu")
    stale = await reject(wiki.moderator, proposal, version=7)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "proposal.version_conflict"
    assert stale.json()["error"]["details"] == {"current_version": 1}
    r = await reject(wiki.moderator, proposal, reason="  Passt nicht  ")
    assert r.status_code == 200, r.text
    assert (r.json()["state"], r.json()["decision_reason"]) == ("rejected", "Passt nicht")
    assert (await _page_row(session, page["id"])).content_md == "alt"
    assert (await listed(wiki.editor, wiki.space_id, state="open"))["items"] == []
    rejected = (await listed(wiki.editor, wiki.space_id, state="rejected"))["items"]
    assert [i["id"] for i in rejected] == [str(proposal.id)]


async def test_only_moderators_decide(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="alt")
    proposal = await agent_change(session, wiki, page, "neu")
    for who in ("editor", "editor2"):
        for decide in (accept, reject):
            r = await decide(wiki.clients[who], proposal)
            assert r.status_code == 403, r.text
            assert r.json()["error"]["code"] == "auth.permission_denied"
    # An agent's run never decides, whatever role it holds.
    from app.core.permissions import SpaceRole
    from app.modules.proposals.decisions import ProposalDecisions

    run = await run_actor(session, wiki, "moderator", SpaceRole.MODERATOR)
    with pytest.raises(Exception) as caught:
        await ProposalDecisions(session).accept(run, proposal.id, proposal.version)
    assert getattr(caught.value, "code", None) == "auth.permission_denied"


async def test_a_moved_on_page_needs_the_merge_confirmed(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(
        wiki.editor, wiki.space_id, "Regeln", content_md="eins\nzwei\ndrei\nvier\n"
    )
    proposal = await agent_change(session, wiki, page, "EINS\nzwei\ndrei\nvier\n")
    saved = await wiki.editor.patch(
        f"/api/pages/{page['id']}",
        json={"version": page["version"], "content_md": "eins\nzwei\ndrei\nVIER\n"},
    )
    current_version = saved.json()["version"]
    one = await detail(wiki.moderator, proposal)
    assert one["current_content_md"] == "eins\nzwei\ndrei\nVIER\n"
    assert one["page_version"] == current_version
    assert one["merge"]["clean"] is True
    assert one["merge"]["merged_content"] == "EINS\nzwei\ndrei\nVIER\n"
    first = await accept(wiki.moderator, proposal)
    assert first.status_code == 409, first.text
    error = first.json()["error"]
    assert error["code"] == "proposal.base_outdated"
    assert error["details"]["current_version"] == current_version
    assert error["details"]["merged_content"] == "EINS\nzwei\ndrei\nVIER\n"
    assert error["details"]["too_large"] is False
    assert (await _page_row(session, page["id"])).content_md == "eins\nzwei\ndrei\nVIER\n"
    stale = await accept(
        wiki.moderator,
        proposal,
        merged_content=error["details"]["merged_content"],
        page_version=current_version - 1,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "proposal.base_outdated"
    done = await accept(
        wiki.moderator,
        proposal,
        merged_content=error["details"]["merged_content"],
        page_version=current_version,
    )
    assert done.status_code == 200, done.text
    assert (await _page_row(session, page["id"])).content_md == "EINS\nzwei\ndrei\nVIER\n"


async def test_a_conflict_is_never_applied_silently(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="a\nb\nc")
    proposal = await agent_change(session, wiki, page, "a\nvorgeschlagen\nc")
    await wiki.editor.patch(
        f"/api/pages/{page['id']}", json={"version": page["version"], "content_md": "a\njetzt\nc"}
    )
    r = await accept(wiki.moderator, proposal)
    assert r.status_code == 409
    details = r.json()["error"]["details"]
    assert details["merged_content"] is None
    assert details["segments"] == [
        {"kind": "clean", "lines": ["a"]},
        {"kind": "conflict", "base": ["b"], "proposed": ["vorgeschlagen"], "current": ["jetzt"]},
        {"kind": "clean", "lines": ["c"]},
    ]
    one = await detail(wiki.moderator, proposal)
    assert one["merge"]["clean"] is False and one["merge"]["merged_content"] is None
    assert one["merge"]["segments"][1]["kind"] == "conflict"
    assert (await _page_row(session, page["id"])).content_md == "a\njetzt\nc"
    resolved = await accept(
        wiki.moderator,
        proposal,
        merged_content="a\nbeides\nc",
        page_version=details["current_version"],
    )
    assert resolved.status_code == 200, resolved.text
    assert (await _page_row(session, page["id"])).content_md == "a\nbeides\nc"


async def test_no_ai_and_trash_refuse_an_agent_change(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="alt")
    proposal = await agent_change(session, wiki, page, "neu")
    locked = await wiki.moderator.put(
        f"/api/pages/{page['id']}/ai-lock", json={"no_ai": True, "version": page["version"]}
    )
    assert locked.status_code == 200, locked.text
    r = await accept(wiki.moderator, proposal)
    assert r.status_code == 409 and r.json()["error"]["code"] == "proposal.page_no_ai"
    with pytest.raises(NotFound):  # AI may not read it: nothing to propose on
        await agent_change(session, wiki, page, "anders")
    unlocked = await wiki.moderator.put(
        f"/api/pages/{page['id']}/ai-lock",
        json={"no_ai": False, "version": locked.json()["version"]},
    )
    trashed = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": unlocked.json()["version"]}
    )
    assert trashed.status_code == 204, trashed.text
    r = await accept(wiki.moderator, proposal)
    assert r.status_code == 404 and r.json()["error"]["code"] == "proposal.not_found"
    assert (await listed(wiki.moderator, wiki.space_id))["items"] == []


async def test_a_new_page_is_created_on_acceptance(wiki: Wiki, session: AsyncSession) -> None:
    parent = await new_page(wiki.editor, wiki.space_id, "Handbuch")
    proposal = await agent_new(session, wiki, "Urlaub", "So geht Urlaub.", parent)
    top = await agent_new(session, wiki, "Ganz oben", "Inhalt")
    one = await detail(wiki.editor, proposal)
    assert (one["kind"], one["title"], one["parent_id"], one["page_id"]) == (
        "new",
        "Urlaub",
        parent["id"],
        None,
    )
    assert one["diff"] == [{"kind": "insert", "lines": ["So geht Urlaub."]}]
    r = await accept(wiki.moderator, proposal)
    assert r.status_code == 200, r.text
    created = await _page_row(session, r.json()["page_id"])
    assert (created.title, created.content_md, created.parent_id) == (
        "Urlaub",
        "So geht Urlaub.",
        uuid.UUID(parent["id"]),
    )
    assert (created.status, created.created_by_type) == ("draft", "agent")
    assert r.json()["result_version"] == 1
    trashed = await wiki.moderator.post(
        f"/api/pages/{parent['id']}/trash", json={"version": parent["version"]}
    )
    assert trashed.status_code == 204
    orphan = await agent_new(session, wiki, "Waise", "x", None)
    assert (await accept(wiki.moderator, top)).status_code == 200
    assert (await accept(wiki.moderator, orphan)).status_code == 200


async def test_a_new_page_under_a_trashed_parent_is_refused(
    wiki: Wiki, session: AsyncSession
) -> None:
    parent = await new_page(wiki.editor, wiki.space_id, "Handbuch")
    proposal = await agent_new(session, wiki, "Urlaub", "x", parent)
    trashed = await wiki.moderator.post(
        f"/api/pages/{parent['id']}/trash", json={"version": parent["version"]}
    )
    assert trashed.status_code == 204
    r = await accept(wiki.moderator, proposal)
    assert r.status_code == 409 and r.json()["error"]["code"] == "proposal.parent_gone"


async def test_making_a_proposal_checks_its_input(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="alt")
    service = ProposalService(session)
    actor = await run_actor(session, wiki)
    pid = uuid.UUID(page["id"])
    cases = [
        ({"content_md": "alt", "reason": "x"}, "proposal.no_change"),
        ({"content_md": "neu", "reason": "  "}, "proposal.invalid_reason"),
        ({"content_md": "neu", "reason": "x" * 301}, "proposal.invalid_reason"),
        ({"content_md": "n" * 200_001, "reason": "x"}, "proposal.invalid_content"),
        ({"content_md": "a\x00b", "reason": "x"}, "proposal.invalid_content"),
    ]
    for args, code in cases:
        with pytest.raises(ValidationFailed) as caught:
            await service.propose_change(actor, pid, author=AGENT, **args)  # type: ignore[arg-type]
        assert caught.value.code == code
    someone_else = Principal.user(wiki.users["viewer"].id)
    with pytest.raises(ValidationFailed) as caught:
        await service.propose_change(actor, pid, "neu", "x", author=someone_else)
    assert caught.value.code == "proposal.bad_author"
    with pytest.raises(ValidationFailed) as caught:
        await service.propose_new(actor, wiki.space.id, None, " ", "x", "y", author=AGENT)
    assert caught.value.code == "proposal.invalid_title"


async def test_a_person_proposes_and_withdraws(wiki: Wiki, session: AsyncSession) -> None:
    """People's proposals have no route in M6; the service takes them (a viewer, who
    sees only their own and only on published pages)."""
    page = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="alt")
    )
    viewer = await actor_of(session, wiki.users["viewer"])
    me = viewer.principal
    service = ProposalService(session)
    mine = await service.propose_change(viewer, uuid.UUID(page["id"]), "neu", "Bitte", author=me)
    seen = (await listed(wiki.viewer, wiki.space_id))["items"]
    assert [(i["id"], i["ai"], i["author"]["name"]) for i in seen] == [
        (str(mine.id), False, wiki.users["viewer"].name)
    ]
    r = await accept(wiki.moderator, mine)
    assert r.status_code == 200
    newest = (await wiki.editor.get(f"/api/pages/{page['id']}/versions")).json()["items"][0]
    assert (newest["source"], newest["author"]["id"], newest["ai"]) == ("human", str(me.id), False)
    other = await service.propose_change(
        viewer, uuid.UUID(page["id"]), "noch neuer", "x", author=me
    )
    withdrawn = await service.withdraw(viewer, other.id, other.version, author=me)
    assert (withdrawn.state, withdrawn.decided_by_id) == ("withdrawn", me.id)
    out = await detail(wiki.viewer, other)
    assert (out["state"], out["decided_by"]["id"]) == ("withdrawn", str(me.id))


async def test_an_agent_withdraws_its_own_proposal_only(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="alt")
    proposal = await agent_change(session, wiki, page, "neu")
    actor = await run_actor(session, wiki)
    service = ProposalService(session)
    with pytest.raises(Exception) as caught:
        await service.withdraw(actor, proposal.id, 1, author=Principal.agent(uuid.uuid4()))
    assert getattr(caught.value, "code", None) in ("proposal.not_found", "auth.permission_denied")
    withdrawn = await service.withdraw(actor, proposal.id, 1, author=AGENT)
    assert withdrawn.state == "withdrawn"
    row = await session.get(PageProposal, proposal.id)
    assert row is not None and row.decided_at is not None


async def test_the_space_says_whether_agents_write_directly(
    wiki: Wiki, session: AsyncSession
) -> None:
    space = (await wiki.moderator.get(f"/api/spaces/{wiki.space_id}")).json()
    assert space["agent_write_policy"] == "propose"
    service = ProposalService(session)
    actor = await run_actor(session, wiki)
    assert await service.agent_writes_directly(actor, wiki.space.id) is False
    denied = await wiki.moderator.patch(
        f"/api/spaces/{wiki.space_id}",
        json={"agent_write_policy": "direct", "version": space["version"]},
    )
    assert denied.status_code == 403  # space.manage only
    admin = await wiki.admin.patch(
        f"/api/spaces/{wiki.space_id}",
        json={"agent_write_policy": "direct", "version": space["version"]},
    )
    assert admin.status_code == 200, admin.text
    assert admin.json()["agent_write_policy"] == "direct"
    assert await service.agent_writes_directly(actor, wiki.space.id) is True
    bad = await wiki.admin.patch(
        f"/api/spaces/{wiki.space_id}", json={"agent_write_policy": None, "version": 2}
    )
    assert bad.status_code == 422
    elsewhere = await actor_of(session, wiki.users["outsider"])
    with pytest.raises(NotFound):
        await service.agent_writes_directly(elsewhere, wiki.space.id)
