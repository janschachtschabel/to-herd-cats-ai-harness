"""Drafts stay with those who may edit (spec 5.6, review M6 finding 1): a run reads
pages only as a viewer of the space would where its answer is read by more than the
asker (a channel, page or ticket thread, a DM of several people), so a draft never
reaches such a place, neither as content nor as a title or a snippet. Only in the DM
of the person alone with the agent does the run see drafts as the person does."""

from typing import Any

import pytest

from app.core.access import Action, can
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.models import StopReason
from app.modules.agents.toolbox import listing, reading, wiki_tools
from app.modules.agents.toolbox.base import NOT_FOUND
from app.modules.spaces.repository import SpaceRepository
from tests.factories_tools import call, tool_context
from tests.factories_wiki import new_page
from tests.factories_writing import Work
from tests.test_run_scope_places import dm_of

SECRET = "GEHEIMER-ENTWURF-42"


async def _channel(work: Work) -> str:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "werkbank"})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _viewer(work: Work, who: str) -> None:
    user = work.bench.people.users[who]
    repo = SpaceRepository(work.bench.session)
    await repo.set_member(work.space.id, Principal.user(user.id), SpaceRole.VIEWER)


async def _draft(work: Work) -> dict[str, Any]:
    draft = await new_page(work.admin, work.space.id, "Entwurf Okapi", content_md=SECRET)
    assert draft["status"] == "draft"
    return draft


async def test_a_draft_does_not_reach_a_channel_viewers_read(work: Work) -> None:
    """An editor asks in a channel of the space; viewers read the answer there."""
    bench, channel = work.bench, await _channel(work)
    await _viewer(work, "bob")
    draft = await _draft(work)
    assert (await bench.people.bob.get(f"/api/pages/{draft['id']}")).status_code == 404
    r = await bench.people.alice.post(
        f"/api/conversations/{channel}/messages",
        json={"body_md": "@Ava lies den Entwurf", "mentions": [str(bench.agent.id)]},
    )
    assert r.status_code == 201 and r.json()["agent_run"]["id"], r.text
    bench.stub.state.replies.append(call("read_page", page_id=draft["id"]))
    bench.stub.state.replies.append({"content": "Nichts gefunden."})
    assert await bench.run_next() == StopReason.COMPLETED
    assert SECRET not in bench.stub.state.texts()
    seen = await bench.people.bob.get(f"/api/messages/{r.json()['id']}/replies?limit=100")
    assert seen.status_code == 200, seen.text
    assert SECRET not in seen.text


@pytest.mark.parametrize("place", ["channel", "dm_of_several"])
async def test_no_reading_tool_shows_a_draft_where_others_read(work: Work, place: str) -> None:
    bench = work.bench
    draft = await _draft(work)
    if place == "channel":
        where: object = await _channel(work)
    else:
        await _viewer(work, "bob")
        where = (await dm_of(bench, "alice", "bob")).id
    ctx = await tool_context(bench, where)
    assert await can(bench.session, ctx.actor, Action.PAGE_EDIT, work.space.id)
    page = reading.ReadPageArgs(page_id=draft["id"])
    assert (await reading.read_page(ctx, page)).text == NOT_FOUND
    found = await reading.search(ctx, reading.SearchArgs(query="Okapi"))
    assert "Entwurf" not in found.text and SECRET not in found.text
    tree = await listing.list_tree(ctx, listing.ListTreeArgs(space_id=work.space.id))
    assert "Entwurf" not in tree.text
    versions = listing.ListVersionsArgs(page_id=draft["id"])
    assert (await listing.list_versions(ctx, versions)).text == NOT_FOUND
    change = wiki_tools.UpdatePageArgs(page_id=draft["id"], content_md="neu", reason="r")
    assert SECRET not in (await wiki_tools.update_page(ctx, change)).text
    assert not ctx.reads.pages


async def test_alone_with_the_agent_the_person_reads_drafts(work: Work) -> None:
    draft = await _draft(work)
    ctx = await tool_context(work.bench)
    page = reading.ReadPageArgs(page_id=draft["id"])
    assert SECRET in (await reading.read_page(ctx, page)).text
    assert "Entwurf" in (await reading.search(ctx, reading.SearchArgs(query="Okapi"))).text
    tree = await listing.list_tree(ctx, listing.ListTreeArgs(space_id=work.space.id))
    assert "Entwurf Okapi" in tree.text and "(draft)" in tree.text
