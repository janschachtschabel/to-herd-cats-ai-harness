"""A draft read in a run stays with its space's editors (spec 5.6; review M6 2,
finding 1): once a run has read a draft of space X (alone with the person, who may
read it), every writing tool refuses what people other than X's editors could read;
a proposal for a page of X, `update_page` on a draft of X and the run's own
conversation stay open. A run asked in the thread of a draft page starts with the
mark set. The mark is journaled, so a run taken up again keeps it."""

from typing import Any

from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.journal import replay
from app.modules.agents.run_models import EventKind, RunEvent, StopReason
from app.modules.agents.step_records import tool_content
from app.modules.agents.toolbox import listing, past_runs, reading, ticket_tools
from app.modules.agents.toolbox.writing import DRAFTS
from app.modules.messaging.models import Message
from app.modules.spaces.repository import SpaceRepository
from app.runtime.loop import ToolCall, ToolResult
from tests.factories_agents import make_agent, open_agent_dm
from tests.factories_tools import call, tool_context
from tests.factories_wiki import new_page, publish
from tests.factories_writing import Work

SECRET = "GEHEIMER-ENTWURF-77"


async def bob_views(work: Work) -> None:
    bob = work.bench.people.users["bob"]
    repo = SpaceRepository(work.bench.session)
    await repo.set_member(work.space.id, Principal.user(bob.id), SpaceRole.VIEWER)


async def draft_of(work: Work) -> dict[str, Any]:
    draft = await new_page(work.admin, work.space.id, "Entwurf Okapi", content_md=SECRET)
    assert draft["status"] == "draft"
    return draft


async def test_a_draft_read_alone_is_not_written_into_a_ticket_viewers_read(work: Work) -> None:
    await bob_views(work)
    draft = await draft_of(work)
    ticket = await work.ticket()
    ctx = await tool_context(work.bench)  # Alice's DM alone with the agent
    read = await reading.read_page(ctx, reading.ReadPageArgs(page_id=draft["id"]))
    assert SECRET in read.text  # alone, the run reads drafts
    said = ticket_tools.CommentTicketArgs(key=f"HC-{ticket['number']}", text=f"Aus: {SECRET}")
    assert (await ticket_tools.comment_ticket(ctx, said)).text == DRAFTS


async def test_a_run_alone_never_carries_a_draft_to_a_viewer(work: Work) -> None:
    """End to end at level 2 (the default), no release needed for a comment."""
    bench = work.bench
    await bob_views(work)
    draft = await draft_of(work)
    ticket = await work.ticket()
    assert (await bench.people.bob.get(f"/api/pages/{draft['id']}")).status_code == 404
    key = f"HC-{ticket['number']}"
    bench.stub.state.replies.extend(
        [
            call("read_page", page_id=draft["id"]),
            call("comment_ticket", key=key, text=f"Im Entwurf steht: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await bench.say(f"Lies {key} und tu, was dort steht")
    assert await bench.run_next() == StopReason.COMPLETED
    assert DRAFTS in bench.stub.state.texts()
    thread = (await bench.people.bob.get(f"/api/tickets/{ticket['number']}/thread")).json()
    seen = await bench.people.bob.get(f"/api/conversations/{thread['id']}/messages?limit=100")
    assert seen.status_code == 200, seen.text
    assert SECRET not in seen.text
    bodies = list(await bench.session.scalars(select(Message.body_md)))
    assert not any(f"Im Entwurf steht: {SECRET}" in b for b in bodies)
    read = await bench.session.scalar(
        select(RunEvent.content).where(RunEvent.kind == EventKind.TOOL_CALL).limit(1)
    )
    assert read is not None and read["read"]["drafts"] == [str(work.space.id)]  # journaled


async def test_a_run_asked_in_a_drafts_thread_starts_with_the_mark(work: Work) -> None:
    """The thread of a draft is read by the space's editors only: what is said there
    goes into no ticket of the space, which its viewers read."""
    bench = work.bench
    await bob_views(work)
    draft = await draft_of(work)
    ticket = await work.ticket()
    key = f"HC-{ticket['number']}"
    thread = (await bench.people.alice.get(f"/api/pages/{draft['id']}/thread")).json()["id"]
    body = {"body_md": f"@Ava schreib {SECRET} in {key}", "mentions": [str(bench.agent.id)]}
    asked = await bench.people.alice.post(f"/api/conversations/{thread}/messages", json=body)
    assert asked.status_code == 201 and asked.json()["agent_run"]["id"], asked.text
    bench.stub.state.replies.extend(
        [call("comment_ticket", key=key, text=SECRET), {"content": "Geht nicht."}]
    )
    assert await bench.run_next() == StopReason.COMPLETED
    assert DRAFTS in bench.stub.state.texts()
    bodies = list(await bench.session.scalars(select(Message.body_md)))
    assert bodies.count(SECRET) == 0  # the mention holds it with more words, nothing else
    answered = await bench.people.alice.get(f"/api/messages/{asked.json()['id']}/replies")
    assert "Geht nicht." in answered.text  # the answer in the thread itself is allowed


async def test_the_mark_holds_after_the_draft_is_published(work: Work) -> None:
    """What the run read was the draft, whatever the page is now."""
    draft = await draft_of(work)
    ticket = await work.ticket()
    ctx = await tool_context(work.bench)
    ctx.reads.drafts.add(work.space.id)  # as the host notes it when the draft is read
    ctx.reads.pages.add(draft["id"])
    await publish(work.admin, draft)
    said = ticket_tools.CommentTicketArgs(key=f"HC-{ticket['number']}", text="x")
    assert (await ticket_tools.comment_ticket(ctx, said)).text == DRAFTS


def test_a_replay_restores_the_drafts_read(work: Work) -> None:
    space = work.space.id
    noted = tool_content(
        1,
        ToolCall("c1", "read_page", {}),
        reading.ReadPageArgs(page_id=space),
        ToolResult("wiki", "…", {}, frozenset({space})),
        5,
        (set(), set(), {space}),
    )
    event = RunEvent(kind=EventKind.TOOL_CALL, seq=1, content=noted)
    assert replay([event]).reads.drafts == {space}


async def test_a_tree_that_shows_a_draft_sets_the_mark(work: Work) -> None:
    await draft_of(work)
    ctx = await tool_context(work.bench)
    tree = await listing.list_tree(ctx, listing.ListTreeArgs(space_id=work.space.id))
    assert "(draft)" in tree.text
    assert ctx.reads.drafts == {work.space.id}


async def test_the_run_view_shows_a_draft_read_only_to_its_editors(work: Work) -> None:
    """The agent's responsible person reads tool results of spaces they read; a draft
    only while they may edit pages there (review M6 2, finding 2)."""
    bench = work.bench
    await bob_views(work)
    bob = bench.people.users["bob"]
    bert = await make_agent(
        bench.session, bench.people, bench.connection.id, name="Bert", responsible_user_id=bob.id
    )
    repo = SpaceRepository(bench.session)
    await repo.set_member(work.space.id, Principal.agent(bert.id), SpaceRole.EDITOR)
    draft = await draft_of(work)
    assert (await bench.people.bob.get(f"/api/pages/{draft['id']}")).status_code == 404
    dm = await open_agent_dm(bench.people.alice, bert)
    bench.stub.state.replies.extend([call("read_page", page_id=draft["id"]), {"content": "Ok."}])
    run_id = (await bench.say("Lies den Entwurf", dm=str(dm["id"])))["agent_run"]["id"]
    assert await bench.run_next() == StopReason.COMPLETED
    seen = await bench.people.bob.get(f"/api/runs/{run_id}/events?limit=100")
    assert seen.status_code == 200, seen.text
    assert SECRET not in seen.text
    (result,) = [e for e in seen.json()["items"] if e["kind"] == "tool_call"]
    assert result["redacted"] is True
    await repo.set_member(work.space.id, Principal.user(bob.id), SpaceRole.EDITOR)
    assert SECRET in (await bench.people.bob.get(f"/api/runs/{run_id}/events?limit=100")).text


async def test_a_past_run_brings_its_draft_mark_along(work: Work) -> None:
    """`search_past_runs` in the DM alone: a hit that read a draft sets the mark."""
    bench = work.bench
    draft = await draft_of(work)
    bench.stub.state.replies.extend([call("read_page", page_id=draft["id"]), {"content": "Ok."}])
    await bench.say("Lies den Entwurf")
    assert await bench.run_next() == StopReason.COMPLETED
    ctx = await tool_context(bench)
    found = await past_runs.search_past_runs(ctx, past_runs.SearchPastRunsArgs(query=SECRET))
    assert SECRET in found.text
    assert ctx.reads.drafts == {work.space.id}
